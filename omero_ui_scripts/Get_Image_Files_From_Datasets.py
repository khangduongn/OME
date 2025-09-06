'''
Author: 
    Khang Duong

Last Updated: 
    11/26/2024

Description: 
    This Omero script allows the user to obtain the filenames and ids of the images in Omero dataset(s).
    After running this script, a csv file of the filenames and ids of the images in the dataset(s) will appear in the corresponding dataset(s) under the "Attachments" section. 
    The csv file has the filename "<dataset-name>_image_files.csv"

    NOTE: This script can only be ran in the Omero Script UI under the custom_scripts tab

    INSTRUCTIONS ON HOW TO DEPLOY THIS SCRIPT:
        1. Make sure that the script is mounted to the Omero server scripts directory in the Docker container
            Add this bind mount to the volumes section in the docker compose file that is creating the Omero server Docker container
            "<path-to-directory-with-script-in-host-server>:/opt/omero/server/OMERO.server/lib/scripts/omero/custom_scripts:ro"
        2. Restart the Docker containers
        3. When you are logged in to the Omero website, you should see the gears icon on the top right corner of the interface (close to the search bar). Click on the icon and you should see a "custom_scripts" tab if done correctly
    INSTRUCTIONS ON HOW TO RUN THIS SCRIPT:
        1. When you are logged in to the website, you should see the gears icon on the top right corner of the interface (close to the search bar). Click on the icon.
        2. Select "custom_scripts"
        3. Select "Get Image Files From Datasets". The interface for the script should appear.
        4. Enter the ID(s) of the dataset(s) where you want to retrieve the filenames and ids of the images, separated by a comma (only needed if you are doing this for multiple datasets). There is a shortcut where you can select the dataset(s) before clicking on the gears icon, which will fill in the IDs entry without you having to enter the IDs yourself.
        5. Click "Run Script" once you have the dataset ID(s) entered
        6. After the script finishes running, you should see a message displaying the results.
        7. Click on the dataset and look at the "Attachments" tab, where you should see the csv file generated with the filenames. The file is usually called "<dataset_name>_image_files.csv"
'''

#import modules
import omero
from omero.gateway import BlitzGateway
from omero.rtypes import rstring, rlong
import omero.scripts as scripts
from omero.cmd import Delete2
import tempfile
import os


def attach_csv_file(conn, dataset, image_files) -> str:
    '''
    Description:
        This function writes the image filenames and ids to the csv file to attach it to the dataset
    Input:
        conn - the object used for establishing a connection with the Omero server
        dataset - the Omero dataset object that the csv file will get attached to
        filenames - the list of filenames in the dataset
    Output:
        message - a message indicating the result of the function 
    '''

    # create the temp directory and then temp file to write the csv data
    tmp_dir = tempfile.mkdtemp(prefix='Dataset_Image_Files')
    (fd, tmp_file) = tempfile.mkstemp(dir=tmp_dir, text=True)
    tfile = os.fdopen(fd, 'w')

    #this function to writes a line to the csv file
    def to_csv(ll):
        nl = len(ll)
        fmstr = "{}, "*(nl-1)+"{}\n"
        return fmstr.format(*ll)

    #construct the header of the csv file
    header = ['Filename', 'Id']
    tfile.write(to_csv(header))

    #write the filename and id for each image to the csv file
    for image_file in image_files:
        row = [image_file[0], image_file[1]]
        tfile.write(to_csv(row))
    tfile.close()

    #generate the name for the csv file
    name = "{}_image_files.csv".format(dataset.getName())

    #link the csv file to the dataset
    ann = conn.createFileAnnfromLocalFile(
        tmp_file, origFilePathAndName=name,
        ns='Dataset_Image_Files')
    ann = dataset.linkAnnotation(ann)

    #remove the temp file and temp directory
    os.remove(tmp_file)
    os.rmdir(tmp_dir)

    return f"Done attaching csv to dataset with id: {dataset.getId()}"


def run_script():

    client = scripts.client(
        'Get Image Filenames and Ids in Dataset(s)',
        "This script returns the list of filenames and ids of the images in the dataset(s).",
        scripts.List(
            "Dataset IDs", optional=False, grouping="1",
            description="Dataset IDs").ofType(rlong(0)),
        authors=["Khang Duong"],
        institutions=["Drexel ANS"],
    )

    try:

        #wrap client to use the Blitz Gateway
        conn = BlitzGateway(client_obj=client)
        print("Connection Established")

        #get the dataset ids from client
        ids = client.getInput("Dataset IDs", unwrap=True)
        print(f"Dataset IDs: {ids}")

        #get the dataset objects
        datasets = list(conn.getObjects("Dataset", ids))
        print("Dataset(s):")
        print(datasets)

        #if the datasets don't exist
        if len(datasets) == 0:
            client.setOutput("Message", rstring("No Dataset Found"))
            raise Exception("No Dataset Found")
            
        processed_dataset_ids = [] #store the dataset ids of the processed datasets

        #for each dataset
        for ds in datasets:

            # name of the file
            csv_name = "{}_image_files.csv".format(ds.getName())
            print(csv_name)

            # remove the csv if it exists
            for ann in ds.listAnnotations():
                if isinstance(ann, omero.gateway.FileAnnotationWrapper):
                    if ann.getFileName() == csv_name:
                        # if the name matches delete it
                        try:
                            delete = Delete2(
                                targetObjects={'FileAnnotation':
                                               [ann.getId()]})
                            handle = conn.c.sf.submit(delete)
                            conn.c.waitOnCmd(
                                handle, loops=10,
                                ms=500, failonerror=True,
                                failontimeout=False, closehandle=False)
                            print("Deleted existing csv")
                        except Exception as ex:
                            print("Failed to delete existing csv: {}".format(
                                ex.message))
                else:
                    print("No exisiting file")

            #get the filenames and ids of the images
            image_files = []
            for img in ds.listChildren():
                image_files.append([img.getName(), img.getId()])

            #attach the image_files data to csv file
            message = attach_csv_file(conn, ds, image_files)
            print(message)

            processed_dataset_ids.append(str(ds.getId()))

        #print message after script finishes
        datasets_ids_text_list = ", ".join(processed_dataset_ids)
        client.setOutput("Message", rstring(f'The script has finished. Check the "Attachments" tab under the datasets with these ids: {datasets_ids_text_list}'))

    finally:
        client.closeSession()


if __name__ == "__main__":
    run_script()