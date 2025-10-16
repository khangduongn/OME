'''
Author: 
    Khang Duong

Last Updated: 
    4/26/2025

Description: 
    This script allows the user to get all image names from all datasets into a csv file (which will be saved in the tmp directory of the Docker Omero server)
'''

#import modules
from omero.gateway import BlitzGateway
import csv
import argparse
import logging
import sys
import os

parser = argparse.ArgumentParser(description = 'Get Image Names From Datasets')
parser.add_argument('-u', '--username', type=str, required=True, help='Omero username that has all of the images and datasets')
parser.add_argument('-w', '--password', type=str, required=True, help='Omero password for the username provided')
parser.add_argument('-c', '--csv-name', type=str, required=True, help='Name of the new csv file will be generated to store all images with their dataset names')
parser.add_argument('-v','--verbose', action='store_true', required=False, help='Enable verbose mode (Prints out information as the script is running)')
args = parser.parse_args()

if __name__=='__main__':

    #create logger
    logger = logging.getLogger()
    
    #if verbose is set, allow more information to be logged
    if args.verbose:
        logger.setLevel(logging.INFO)
    else:
        #otherwise only display errors/warnings
        logger.setLevel(logging.WARNING)
    

    #create a stream handler and ensure that all messages are printed to stdout
    streamHandler = logging.StreamHandler()
    streamHandler.setLevel(logger.level)  

    #create a formatter and set the formatter for the handler
    formatter = logging.Formatter("%(asctime)s - %(levelname)-8s: %(message)s")
    streamHandler.setFormatter(formatter)
    
    #add the handler to the logger
    logger.addHandler(streamHandler)

    logging.info(f"Starting the script. Getting all image names and datasets from the user {args.username}.")

    try:

        #connect to omero
        with BlitzGateway(args.username, args.password, host="localhost", port=4064, secure=True) as conn:

            #open csv file
            with open(os.path.join('/tmp', args.csv_name), mode='w', newline='', encoding='utf-8') as file:
                csv_writer = csv.writer(file)
                
                # write header
                csv_writer.writerow(['Image Name', 'Dataset Name'])

                #get all datasets
                datasets = conn.getObjects('Dataset')

                for dataset in datasets:
                    dataset_name = dataset.getName()

                    #get all images inside this dataset
                    images = list(dataset.listChildren())

                    for image in images:
                        image_name = image.getName()

                        # Write a row in CSV
                        csv_writer.writerow([image_name, dataset_name])

    except Exception as error:
        print(f"Error: Unable to get image names from datasets. The following error occurred: {error}", file = sys.stderr)
        exit(1)