'''
Author: 
    Khang Duong

Last Updated: 
    11/5/2023

Description: 
    This script allows the user to stitch a collection of image tiles into a mosaic image and save this mosaic
    image as an OME-TIFF file that can be imported into OMERO for viewing. This script also works for images
    with multiple z planes

Future Improvements:
    TODO: Validate inputs fixes
    TODO: May need to add support for multiple image stitching. Multiprocessing of images
    TODO: This script only works for grayscale images. Need to add support for other image types
    TODO: This script only works for the following compression types: None, JPEG, JPEG2000 (Lossy and Lossless). Add support for other types
   
    TODO: Add support for reading different tile file format and RGB images
    TODO: Add some error messages for when the user enters invalid parameters
    TODO: Allow user to set location of the flagged csv file containing problematic images

    NOTE: This script assumes that each tile has the same size
'''

#import modules
#make sure you have these modules installed on the current environment
import cv2
import numpy as np
import os
import argparse
import tifffile
import time
import pandas as pd
import uuid
import glob
from math import floor
import csv
from skimage.metrics import structural_similarity as ssim
from concurrent.futures import ThreadPoolExecutor

parser = argparse.ArgumentParser(description = 'Stitch tiles and save as OME-TIFF')

parser.add_argument('-c', '--compression', type=str, default='None', metavar='', required=False, help='Compression Type (e.g., JPEG, JPEG2000, None)')
parser.add_argument('-q', '--quality', type=int, default=80, metavar='', required=False, help='Quality factor for JPEG or JPEG2000 compression')
parser.add_argument('-od', '--output-dir', type=str, metavar='', required=True, help='Path of the directory that will contain the converted images (if directory does not exist, then one will be created)')
parser.add_argument('-id', '--input-dir', type=str, metavar='', required=True, help='Path of the directory containing the tiles to stitch')
parser.add_argument('-pr', '--pyramid-resolutions', type=int, default=3, metavar='', required=False, help='Number of pyramid levels (not including full resolution image) (Default: 3) (Setting this to 0 means that the image will only be the full resolution image)')
parser.add_argument('-ps', '--pyramid-scale', type=int, default=4, metavar='', required=False, help='Pyramid scale (Default: 4)')
parser.add_argument('-t', '--tile-size', type=int, nargs=2, default = [256,256], metavar=('xPixels', 'yPixels'), required=False, help='Tile size')
parser.add_argument('-bg','--bigtiff', action='store_true', required=False, help='Save the output image as BigTiff')
parser.add_argument('-d','--debug', action='store_true', required=False, help='Enable debug mode (Helps to determine if stitching worked correctly)')


args = parser.parse_args()

def insert_tile(img_stitched, tiles_path, tileNumber, tilesize_x, tilesize_y, R, Rmax, C, Cmax, Z, ext, overlap ):
    
    if '.tif' in ext:
        tile = tifffile.imread(os.path.join(tiles_path, f'Tile{str(tileNumber).zfill(6)}' + ext))

    else:
        tile = cv2.imread(os.path.join(tiles_path, f'Tile{str(tileNumber).zfill(6)}' + ext), cv2.IMREAD_UNCHANGED)

    

    if (R == Rmax):
        yRange = slice(R * (tilesize_y - overlap), (R + 1) * (tilesize_y - overlap) + overlap)
    else:
        yRange = slice(R * (tilesize_y - overlap), (R + 1) * (tilesize_y - overlap))
        tile = tile[0:(tilesize_y - overlap), :]

    if (R % 2 == 0):

        if (C == Cmax):
            xRange = slice(C * (tilesize_x - overlap), (C + 1) * (tilesize_x - overlap) + overlap)
        else:
            xRange = slice(C * (tilesize_x - overlap), (C + 1) * (tilesize_x - overlap))
            tile = tile[:, 0:(tilesize_x - overlap)]
    else:

        if (C == 0):
            xRange = slice(0, tilesize_x)
        else:
            xRange = slice((C - 1) * (tilesize_x - overlap) + tilesize_x, (C) * (tilesize_x - overlap) + tilesize_x)
            tile = tile[:, overlap:tilesize_x]

    img_stitched[Z, yRange, xRange]  = tile

def stitch_tiles(tiles_path, output_path):
    '''
    Description:
        This function stitches tiles in a the directory into a mosaic image. The function also works
        for images with multiple z planes

    Input:
        tiles_path - the path to the directory containing the tiles and the XYZPositions.txt file
        output_path - the path to the directory containing the converted images
    Output:
        filename - the filename of the temporary memory-mapped file containing the numpy array of the original stitched image
        img_shape, wMicrons/tile_xsize, hMicrons/tile_ysize
    
    '''

    startTimeStitch = time.time()
    
    print(f'Begin stitching {tiles_path}')

    #try to read the tile information from XYZPositions.txt file
    try:
        XYZdata = pd.read_csv(os.path.join(tiles_path, 'XYZPositions.txt'), encoding = 'UTF-16')

    except:
        raise Exception('Error reading the XYZPositions.txt file. Check to make sure the file exists in the path you provided and is not corrupted.')


    #these columns are hardcoded assuming that the columns of XYZPositions.txt file stay the same
    #change these if necessary
    X_col, Y_col, R_col, C_col, Z_col = XYZdata.columns[1], XYZdata.columns[2], XYZdata.columns[4], XYZdata.columns[5], XYZdata.columns[7]

    wMicrons, hMicrons, tile_xsize, tile_ysize = XYZdata[XYZdata.columns[8]][0], XYZdata[XYZdata.columns[9]][0], XYZdata[XYZdata.columns[10]][0], XYZdata[XYZdata.columns[11]][0]


    R_min, C_min, Z_min = np.min(XYZdata[R_col]), np.min(XYZdata[C_col]), np.min(XYZdata[Z_col])
    R_max = np.max(XYZdata[R_col])
    C_max = np.max(XYZdata[C_col])
    nx, ny, nz = len(XYZdata[C_col].unique()), len(XYZdata[R_col].unique()), len(XYZdata[Z_col].unique())

    Zs_list = sorted(XYZdata[Z_col].unique())

    #get the file extension of the tiles by finding the most common file extension in the folder
    files_ext = [os.path.splitext(file)[1] for file in os.listdir(tiles_path) if file.startswith('Tile')]
    ext = max(files_ext, key=files_ext.count)


    #set the number of pixel overlap between the tiles at 0
    overlap = 0


    #if the image is not a one tile stack
    if nx != 1 and ny != 1:


        #get the number of pixels of overlap between tiles
        min_C = np.min(XYZdata[C_col].loc[(XYZdata[Z_col] == Z_min) & (XYZdata[R_col] == R_min)])

        x_init = XYZdata[X_col].loc[(XYZdata[C_col] == min_C) & (XYZdata[Z_col] == Z_min) & (XYZdata[R_col] == R_min)].values
        x_final = XYZdata[X_col].loc[(XYZdata[C_col] == min_C+1) & (XYZdata[Z_col] == Z_min) & (XYZdata[R_col] == R_min)].values
    
        x_step = float(x_final-x_init)

        overlapMicrons = wMicrons - x_step

        resolution = tile_xsize / wMicrons

        overlap_x = round(resolution * overlapMicrons)
        
        print('X step:', x_step)
        print('X overlap (um):', overlapMicrons)
        print('X resolution (px/um)', resolution)
        print('X overlap (px)', overlap_x)



        #get the number of pixels of overlap between tiles (Y axis)
        min_R = np.min(XYZdata[R_col].loc[(XYZdata[Z_col] == Z_min) & (XYZdata[C_col] == C_min)])

        y_init = XYZdata[Y_col].loc[(XYZdata[C_col] == C_min) & (XYZdata[Z_col] == Z_min) & (XYZdata[R_col] == min_R)].values
        y_final = XYZdata[Y_col].loc[(XYZdata[C_col] == C_min) & (XYZdata[Z_col] == Z_min) & (XYZdata[R_col] == min_R+1)].values

        y_step = float(y_final-y_init)

    
        overlapMicrons = hMicrons - y_step

        resolution = tile_ysize / hMicrons

        overlap_y = round(resolution * overlapMicrons)
        print('Y step:', y_step)
        print('Y overlap (um):', overlapMicrons)
        print('Y resolution (px/um)', resolution)
        print('Y overlap (px)', overlap_y)

        if overlap_x == 16 and overlap_y == 16:
            
            overlap = overlap_x

        else: 
            
            with open(os.path.join(output_path, 'flagged_images.csv'), 'a') as f:
                writer = csv.writer(f)
                writer.writerow([tiles_path, f'# of pixels of overlap in the x and y directions is not 16. It is {overlap_x} in the x direction and {overlap_y} in the y direction.'])

            return 'Flagged'
    
        

    #get the number of pixels for the x, y, and z dimensions of the final stitched image
    stitched_x, stitched_y, stitched_z = (tile_xsize - overlap)*nx + overlap, (tile_ysize-overlap)*ny + overlap, nz


    #store the shape of the final stitched image into the img_shape tuple
    img_shape = (stitched_z, stitched_y, stitched_x)


    #create random name for the temporary memory mapped file to store array (this helps with memory usage for large images)
    filename = os.path.join(output_path, f'{uuid.uuid4().hex}_{os.path.basename(tiles_path)}.dat')


    #store image data to the memory mapped file
    img_stitched = np.memmap(filename, dtype='uint8', mode='w+', shape=img_shape)

    # Number of threads to use
    num_threads = 3

    # Use ThreadPoolExecutor to apply the function to DataFrame rows in parallel
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        # Submit tasks for each row and get futures
        [executor.submit(insert_tile, img_stitched, tiles_path, XYZdata.iloc[i, 0], tile_xsize, tile_ysize, XYZdata.iloc[i, 4], R_max, XYZdata.iloc[i, 5], C_max,  Zs_list.index(XYZdata.iloc[i, 7]), ext, overlap) for i in range(len(XYZdata))]

    
    img_stitched.flush()

    del img_stitched

    print("The shape of the final image is (z, y, x) =", img_shape)

    print("Stitching the tiles took --- %s seconds ---" % (time.time() - startTimeStitch))


    return filename, img_shape, wMicrons/tile_xsize, hMicrons/tile_ysize


    
def validateCompression(compression, quality_factor):


    #if the user chooses uncompressed or none as the compression type
    if (compression.lower().replace(" ", "") in ['none', 'uncompressed']):

        #set the compression parameter as None
        return None
        
    #if the user provides compression and quality parameters
    elif (compression.lower().replace(" ", "") in ['jpeg', 'jpeg2000', 'jpeg-2000']) and (quality_factor > 0):

        #set the compression parameter as the compression type and quality factor
        return (compression, quality_factor)

    else:

        raise Exception("Invalid compression schema or quality factor. Please check your input again")
    


if __name__ == '__main__':



    startTimeScript = time.time()

    #TODO: validate this input so that users cant put negative numbers
    #store the input tile size into designated variables
    tileSizeX, tileSizeY = args.tile_size

    #validate the compression and quality factor inputs and return the compression parameter that will be passed to tifffile
    compression_parameter = validateCompression(args.compression, args.quality) 

    #searches recursively within the input directory for any directories containing the XYZPositions.txt.
    #this assumes that any folder containing the XYZPositions.txt file has all the tiles needed to stitch an image.
    #this basically uses the XYZPositions.txt file as the instruction to stitch the tiles
    #XYZ_path is a list containing the paths of all XYZPositions.txt files in the input directory
    XYZ_path = glob.glob(os.path.join(args.input_dir, '**/XYZPositions.txt'), recursive=True)

    #gets the path of the tile images (basically strips XYZPositions.txt from the directories stored in the list XYZ_path)
    image_paths = [os.path.dirname(img_dir) for img_dir in XYZ_path]

    #if there are no paths stored in the list image_paths (aka no XYZPositions.txt or instruction to stitch to be found)
    if len(image_paths) == 0:

        #then raise an error.
        raise Exception('No XYZPositions.txt file to be found. Make sure this file is in the same directory with the tiles you want to stitch')
    
    outputExtension = '.ome.tiff'

    if args.debug == True:
        args.pyramid_resolutions = 0
        outputExtension = '_debug.ome.tiff'
        compression_parameter = None

    #for each image (tile paths)
    for tiles_path in image_paths:

        startTimeImage = time.time()

        try:

            #generate the path of the stitched image
            outputImagePath = os.path.join(args.output_dir, os.path.basename(tiles_path)+ outputExtension)
            
            #stitch the tiles together 
            results = stitch_tiles(tiles_path, args.output_dir)

            #if the stitching is successful
            if type(results) is tuple:
        
                temp_filename, img_shape, pixSizeX, pixSizeY = results

            
                images = np.memmap(temp_filename, dtype='uint8', mode='r', shape = img_shape)


                print('Begin saving images as OME-TIFF')

                #if the user sets the pyramid resolutions to 0 (no pyramid generation)
                if args.pyramid_resolutions == 0:
                    
                    #save the image without pyramid levels
                    with tifffile.TiffWriter(outputImagePath, bigtiff = args.bigtiff) as writer:
                        writer.write(images,metadata={'axes': 'ZYX', 'PhysicalSizeX': pixSizeX, 'PhysicalSizeXUnit': "µm", 'PhysicalSizeY': pixSizeY, 'PhysicalSizeYUnit': "µm"}, compression = compression_parameter, tile = (tileSizeX, tileSizeY))

                    if args.debug == True:
                        testImg = tifffile.imread(outputImagePath)

                        mosTiffFound = False
                        for name in os.listdir(os.path.dirname(tiles_path)):
                            if os.path.isdir(os.path.join(os.path.dirname(tiles_path), name)) and 'mostif' in os.path.join(os.path.dirname(tiles_path), name).lower():
                                mosTiffFound = True
                                planesPath = os.path.join(os.path.dirname(tiles_path), name)

                                i = 0
                                for planeFile in sorted(glob.glob(os.path.join(planesPath, '*.tif'))):
                                    imgPlane = tifffile.imread(planeFile)

                                    score = ssim(testImg[i], imgPlane)
                                    
                                    if score != 1:
                                        with open(os.path.join(os.path.dirname(args.output_dir), 'flagged_images.csv'), 'a') as f:
                                            writer = csv.writer(f)
                                            writer.writerow([tiles_path, f"Stitched image is not exactly the same as the Mosaic TIFF image. The ssim score is {score}."])
                                        break

                                    i +=1 

                        if not mosTiffFound:
                            with open(os.path.join(os.path.dirname(args.output_dir), 'flagged_images.csv'), 'a') as f:
                                writer = csv.writer(f)
                                writer.writerow([tiles_path, f"Mosaic TIFF image was not found for this image so a comparison is not made and the stitched image is not saved."])

                else:
                    

                    with tifffile.TiffWriter(outputImagePath, bigtiff=args.bigtiff) as tif:
                        
                        options = dict(tile=(tileSizeX, tileSizeY), compression = compression_parameter, 
                            metadata={'axes': 'ZYX', 'PhysicalSizeX': pixSizeX, 'PhysicalSizeXUnit': "µm", 'PhysicalSizeY': pixSizeY, 'PhysicalSizeYUnit':"µm"})
            
                        tif.write(images, subifds=args.pyramid_resolutions, **options)

                        # successively generate and save pyramid levels to the SubIFDs
                        for x in range(args.pyramid_resolutions):
                            
                                
                            tif.write(np.stack([cv2.resize(images[n, :, :], (floor(img_shape[2] * (1/args.pyramid_scale)**(x+1)), floor(img_shape[1] * (1/args.pyramid_scale)**(x+1))),interpolation=cv2.INTER_LINEAR) for n in range(len(images))]), subfiletype=1, **options)

                #remove the temp memory mapped file
                os.remove(temp_filename)

            

                print("Stitching and saving the directory took --- %s seconds ---" % (time.time() - startTimeImage))
                print()

            else:
                print(f"The number of overlapping pixels between tiles is not 16. Please check the image again.")
                print("This process took --- %s seconds ---" % (time.time() - startTimeImage))
                print()
                

        except Exception as e:
            print(f"Error: {e}")
            print(f"Failed to stitch the tiles in the directory {tiles_path}. Check for issues.", end = '\n')
            with open(os.path.join(os.path.dirname(args.output_dir), 'flagged_images.csv'), 'a') as f:
                writer = csv.writer(f)
                writer.writerow([tiles_path, "Can't determine overlap (Problem with stitching)"])
    
    
    
    

    print("This script took --- %s seconds ---" % (time.time() - startTimeScript), end = ' ')
    print()
    print()
    print()
