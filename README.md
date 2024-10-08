# ANS OME Scripts

This repository contains scripts used in the conversion to Omero pipeline. The `conversion.py` script is a Python script used to stitch .tif tile images into full stitched .ome.tiff images that are compatible with the Omero image viewer web application.

## Image Stitching and Conversion

The `conversion.py` script was developed in Python 3.9.18

### Installation

Install [Python](https://www.python.org/downloads/) (make sure the version is compatible with the script)

You can create a virtual environment or use the default environment in Python to install the dependencies needed to run the script. I recommend using a virtual environment to keep all of the dependencies and scripts in the same, contained environment for the project.

You can install all of the dependencies (modules) required to run the script into your Python environment using the following command (the `requirements.txt` file is provided in this repository):

`pip3 install -r requirements.txt`

Navigate into the directory with the script and ensure that the current Python environment you are in has the necessary dependencies to run the script. Run the script using the following command:

`python3 conversion.py -h`

The help flag `-h` will provide you with more information on how to run the script with the required and optional arguments depending on your conversion needs.

### OMERO

[Omero](https://www.openmicroscopy.org/omero/) is an image viewer web application that stores all your images in a secure central repository, where you can view, organize, analyze, and share them from anywhere you have internet access. Read the official [Omero documentation](https://omero.readthedocs.io/en/stable/) to learn how to use Omero and how to best use its features for your needs.

## Setting Up Omero

### Method 1: Docker
Install [Docker](https://docs.docker.com/engine/install/) onto the server that will be running the Omero instance. This server will be responsible for managing the Omero server, web services, and database. Ensure that the server is secure before running Docker and creating the Omero instance. 

Configure Docker to your liking but ensure that the Docker commands can only be executed by users with sudo privileges.

It is recommended to have a user with sudo privileges manage the Docker containers and Omero instance.

The easiest way to get an Omero instance up and running is through using docker compose, which allows you to start a multi-container application quickly. The Omero web application requires three Docker containers to run (Omero server, Omero web, and PostgreSQL database). Install the docker compose files from this [GitHub repository](https://github.com/ome/docker-example-omero). You can clone the repository or just install the ZIP file directly. 

After installing the repository files into a directory, run the following commands using the user with sudo privileges to start the Omero instance.

Change directory into the directory that contains the docker-compose.yml file (you just downloaded this directory):

`cd <directory-with-docker-compose-yml-file>`,

Pull the latest major versions of the containers:

`sudo docker compose pull`

Start the containers:

`sudo docker compose up -d`

The following command is optional as it is only really needed if you want to see the outputs generated by the containers:

`sudo docker compose logs -f`

To stop the docker container, ensure that you are in the same directory containing the docker-compose.yml file and run the following command:

`sudo docker compose down`

Note: Any changes you make within these Docker containers (configs, files, or directories) will get deleted after the containers shut down. To save the changes you make within a container, commit the container with the changes as a new image and run the container using the new image in the future. Look up Docker documentation for more information.

Images imported to Omero or changes made within the Omero web application will get saved when the containers shut down as long as you do not delete the Docker volumes associated with the Omero application.

#### Getting into the container

If you want to make changes to the environment of a Docker container (make new folders, add new configurations, or change the Omero web UI), you can do so using the following command: 

`sudo docker exec -it <container_name_or_id> /bin/bash`

This command lets you go inside the Docker container environment and run commands within the environment to make changes.


#### Mount Volumes

To import images from the host server (the server that is running the Omero Docker containers) to the Omero web application (deployed using the Docker containers), it is recommended that you perform [in-place importing](#in-place-import) to prevent generating duplicate copies of the images. However, to perform in-place importing, it is a more involved process than just running the import commands as you must run these in-place import commands WITHIN the Omero server Docker container, meaning that the images that you want to import must also be mounted to a directory within this container. To mount the images from the host server to the Omero server Docker container, you must use Docker volumes. Read the [documentation](https://docs.docker.com/storage/volumes/) on Docker volumes to learn more about how they work. It is recommended that you modify the docker-compose.yml file to add a volume in the Omero server container that mounts a directory from the host server to a directory in the container. That way, you can run in-place import commands within the Omero server Docker container as these commands only work when ran within the server that is deploying the Omero server (in this case it would be the Omero server Docker container).

### Method 2: Direct Installation

To install Omero directly onto your server without the use of containerization, you can follow the installation instructions on the [Omero System Administrator Documentation page](https://omero.readthedocs.io/en/stable/sysadmins/). This page also gives you resources on how to manage and optimize Omero (recommended for system administrators). You can also install the Omero server using installation scripts available at this [GitHub repository](https://github.com/ome/omero-install). Please read the instructions carefully and ensure you have the required prerequisites and system specifications to install and run Omero. Make sure to install both Omero.server and Omero.web. Currently, there are no official scripts available to easily install Omero.web. You need to follow the instructions provided in the System Administrator Documentation page.

It is more complicated to install and run Omero using this method compared to the Docker method. You should choose the method that works best for your needs.


## Omero Python API

The Omero Python API allows you to connect to an Omero server and retrieve and manipulate image data stored within the server via Python. You can use Python to create scripts that automate tasks required within the Omero server by using the Omero Python API. Install the API and read the [documentation](https://docs.openmicroscopy.org/omero/5.6.0/developers/Python.html) for more information.

## Omero Command Line Interface (CLI) 

The Omero Command Line Interface (Omero.cli) allows you to connect to an Omero server and retrieve and manipulate image data and objects stored within the server via the command line. It has very similar functionalities to the Omero Python API and is bundled with this API or the Omero server during installation. One useful feature of the Omero CLI is that it allows for easy import of images and can support a configuration YAML file used to perform a batch of imports with similar options at once (e.g., import groups of images into their own datasets). Install the Omero CLI and read the [documentation](https://docs.openmicroscopy.org/omero/5.4.6/users/cli/index.html) for more information.

## Importing Images

Read the [documentation](https://omero-guides.readthedocs.io/en/latest/upload/docs/import.html) on how to import images to Omero and choose the type of import that matches your needs.

### In-place Import

It is recommended to use in-place import when you want to import images to your Omero server without making an additional copy of each image file, which would take up additional space on your server. Here are some resources on the different in-place importing methods and examples on how to in-place import using the Omero CLI:
* https://docs.openmicroscopy.org/omero/5.4.5/sysadmins/in-place-import.html
* https://omero-guides.readthedocs.io/en/latest/upload/docs/import-cli.html#in-place-import-using-the-cli


### Bulk Import

It is recommended to use bulk import when you have multiple images that belong to different datasets and you want to import them to their respective datasets all at once. That way, you can take advantage of the configuration YAML file and customize the bullk import to your needs. Here are some resources on how to perform bulk imports as well as some examples:
* https://docs.openmicroscopy.org/omero/5.6.3/users/cli/import-bulk.html
* https://omero-guides.readthedocs.io/en/latest/upload/docs/import-cli.html#bulk-import-using-the-cli


## Omero Scripts

Omero scripts allow you to extend the functionalities of Omero (similar to plugins). They are typically written in Python but can support other languages as well, such as MATLAB and Jython. They can be uploaded to the Omero server and run in the Omero web client with its own UI (configured in the scripts). That way, users using the Omero web client can run the scripts to do their own image processing tasks. For more information on Omero scripts and how to develop your own, read the [documentation](https://docs.openmicroscopy.org/omero/5.4.5/developers/scripts/index.html).







