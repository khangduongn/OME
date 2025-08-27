# ANS Diatom Documentation

## Knowledge Prerequisites
To understand the implementation of the ANS Diatom conversion to import pipeline and to navigate around the ANS servers, you must have knowledge of the following concepts:
* Linux Operating System (OS)
* Docker and Containerization 
* Python
* Basic shell commands 

## System Prerequisites
* To interact with ANS servers, you must have access to the Drexel VPN through Cisco Secure Client, which can be installed here for your OS. Once installed, you can launch the Cisco Secure Client application and connect to the VPN using your Drexel credentials
* You must have access to a terminal/command line on your computer and be able to use the `ssh` command to ssh into the ANS servers.
    * `ssh username@hostname`
        * username: The username you'll use on the remote server. 
        * hostname: The domain name or IP address of the remote server


## Source Code
The source code/configuration files for all ANS Diatom pipelines and systems is located in a GitHub repository, which can be accessed [here](https://github.com/khangduongn/ANS-OME-Scripts).

To make changes to the code, you can make a fork of the repository and then clone that fork into your local computer.

## Conversion to Import Pipeline
### Purpose
The purpose of the conversion to import pipeline is to automate the stitching and conversion of raw Diatom scans into a file format that is compatible with the Omero image viewer web application in order to import them into the application for better viewing and organization of the scans.

### Overview
The pipeline can be broken down into two smaller pipelines:
* **Conversion Pipeline**: Stitch and convert raw Diatom scans (which start out as tiles of images with .tif file format) together to form the full Diatom scans, with the .ome.tiff file format that is compatible with Omero
* **Import Pipeline**: Import the .ome.tiff image files into Omero in order to organize and view them as full scans

### Conversion Pipeline
The conversion pipeline is implemented in Python. It monitors a directory for new raw Diatom scans (in .tif file format) and stitches and converts them into full scans with the .ome.tiff file format compatible in Omero.

The raw scans should get put into a directory where the pipeline can access and read. The raw scans directory is usually in the form <imageName>/<imageName>/scans


### Import Pipeline
The import script is implemented in Python. It monitors a directory for new image files (.ome.tiff file format) that are written to it and imports those images to the Omero server for viewing.

The full scans should be placed into a directory where the pipeline can access and read. The directory is flat with only .ome.tiff files except for one folder labeled Failed to store images that failed to import. These images can be deleted and reconverted to fix the issue. In order to reimport the images that failed to import, place the image back into the Imports folder and the pipeline should automatically detect it and import it to Omero.
 
## System Architecture

### Overview
There are two servers being used for the conversion to import pipeline: 
* The conversion server is used to stitch and convert scans into a format that is compatible with Omero. To log in to the conversion server, you need to use `ssh`.
* The web server is used to host the Omero web application in order view the full Diatom images provided by the conversion server. To log in to the web server, you need to use `ssh`.

The credentials for these servers will be provided to you by ANS IT.

### Image Storage
A network file share is being used to store the raw image scans and then shared with the two servers in order to convert and import the images to Omero.

The conversion server should have access to the network file share via a read-only mounted directory with the raw images scans. It should also have access to a read/write mounted directory to dump the converted files for the web server to read and import.

The web server that is hosting Omero must also have access to the network file share via a read-only mounted directory with the converted image files from the conversion server. The converted image files should permanently be stored in this directory and not moved anywhere else.

The details about these mounts can be obtained by contacting ANS IT.

### Conversion Server
Currently, the conversion pipeline is deployed on the conversion server. The conversion script can be run manually by running conversion.py on raw image scans. To monitor a directory for new tiles to stitch and convert, the script [INSERT SCRIPT NAME] can be run. This script is currently running on the conversion server at all times in a daemon service. The file to manage the service is located in 

### Web Server
Currently, the Omero web application is deployed on the web server. The import.py script can be run to import converted image scans. To monitor a directory for new images to import, you need to run the import_monitor.py script. The monitor script is currently running on the web server at all times in a daemon service. The file to manage the service should have the path `/etc/systemd/system/import.service`. The script looks the mounted read-only directory from the network file share for new images that got converted and import them to the Omero web app. 
 
## Setup
### Installing Python
You must install Python on both the conversion and web servers in order to run Python scripts used in the conversion and import pipelines.
1. It is recommended you install miniconda, which is a lightweight package management system for Python. You can install miniconda for your system [here](https://www.anaconda.com/docs/getting-started/miniconda/install)
2. You can add `conda` to your environment variable so you don't have to type out the full path to conda whenever you want to run a conda command.
    * For example, in Linux, you can do the following:
        1. Open the `~/.bashrc` file with your favorite editor and add the following line to it:
            * `export PATH="</path/to/your/anaconda3/bin>:$PATH"`, replacing `</path/to/your/anaconda3/bin>` with the path to the bin directory where your conda executable is.
        2. Apply the change by running the command `source ~/.bashrc`
3. Create a Python virtual environment to install the libraries needed to manage Omero and run the Python scripts:
    `conda create --name ome python=3.9.13`
4. Activate the virtual environment: `conda activate ome`
5. Install dependencies using the `requirements.txt` that in the [Github repository](https://github.com/khangduongn/ANS-OME-Scripts)
    * `pip3 install -r </path/to/requirements.txt>`, replacing `</path/to/requirements.txt>` with the path to the `requirements.txt` file


### Installing Omero using Docker
Prerequisite:
1. Ensure the server that will be hosting the Omero application is active and secure before installing Omero. This server will be responsible for managing the Omero server, web services, and database. 
2. Install Docker on the host server [here](https://docs.docker.com/engine/install/). 
    * Make sure to select the appropriate installation method for your server operating system.
3. Configure Docker to your liking but ensure that Docker commands can only be executed by users with sudo privileges
    * It is recommended to have a user with sudo privileges manage the Docker containers.

Installation:
1. The easiest way to get an Omero instance up and running is through using docker compose, which allows you to start a multi-container application quickly. Install the docker compose files from this (GitHub repository)[https://github.com/khangduongn/ANS-OME-Scripts]. You can clone the repository or just install the ZIP file directly.
    * An Omero application requires three Docker containers to run (Omero server, Omero web, and PostgreSQL database). 
        * Omero server handles the backend logic
        * Omero web handles the frontend user interface
        * PostgreSQL database stores the data
2. After cloning the repository, `cd` into that repository and into the `docker-omero` directory, which contains the `docker-compose.yml` file in order to start the containers
3. Open the `docker-compose.yml` file using your favorite editor
4. Modify the configuration settings appropriate for your system. View the comments in this file for more information.
    * For example, it is recommended to modify the volume mounts for the image directory and the directory with the `public` application
4. Before you can start the containers, you must build a custom Omero web Docker image, which contains the `public` app used for displaying images to the public. 
5. `cd` into the `custom-omero-web-docker` directory which contains the `Dockerfile` used for building the Docker image for Omero web
6. You can either run `make build` if you have `make` installed on the server. Otherwise, you can run the following commands in order:
    ```
    sudo docker build -t omero-web-customized .
	sudo docker compose -f ../docker-compose.yml down
	sudo docker compose -f ../docker-compose.yml up -d
	sudo docker ps
    ```
    * The first command builds the custom Omero web image
    * The second command shuts down any Omero Docker containers that are currently up 
    * The third command builds the Omer Docker containers
    * The fourth command checks the status of these containers in order to verify that they are running
7. Check to make sure that all three containers are running using `sudo docker ps` before proceeding to the next step 
    * If you want to update any of the Omero docker images, you can run `sudo docker compose pull <name-of-image>`, replacing `<name-of-image>` to the name of the Docker image. 
        * You can't do this with the Omero web image because it is a custom image. You would need to modify the first line of the `Dockerfile` from `FROM openmicroscopy omero-web-standalone:5` to an Omero web image version of your choosing or the latest version. After modifying this file, you will need to rebuild the image again using the commands in Step 6.
8. You can now start the containers by `cd` into the directory with the `docker-compose.yml` file and running the command `sudo docker compose up -d`.
    * The following command is optional as it is only really needed if you want to see the outputs generated by the containers: `sudo docker compose logs -f`
9. To stop the docker containers, ensure that you are in the same directory containing the `docker-compose.yml` file and run the following command:
`sudo docker compose down`
    * **Note**: Any changes you make within these Docker containers (configs, files, or directories) will get deleted after the containers shut down. 
        * To save the changes you make within a container, commit the container with the changes as a new image and run the container using the new image in the future. Look up Docker documentation for more information.
        * Images imported to Omero or changes made within the Omero web application will get saved when the containers shut down as long as you do not delete the Docker volumes associated with the Omero application.

### Getting into the Docker container (For Testing or Development)
If you want to make changes to the environment of a Docker container (make new folders, add new configurations, or change the Omero web UI), you can do so using the following command:
`sudo docker exec -it <container_name_or_id> /bin/bash`, replacing `<container_name_or_id>` with the container name or container id. This command lets you go inside the Docker container environment and run commands within the environment to make changes. These changes will be erased if you shut down the container without committing.

### Create users in Omero
1. Log in as root in the Omero web application to create new users and change root's password
    * The username is `root`, and the password is `omero`. You must change root's password after logging in.
    * You can change the password by logging in as root and clicking on the `Admin` tab at the top navigation bar. Click on the pencil icon next to root and then click on `Change User's Password`.
2. It is recommended to create a `public` group with two users. One user will own the images and the other user will be the public user who can only view the images without logging in.
    * To create a group, click on the `Admin` tab at the top navigation bar, then click `Groups`, and lastly click on the `Add new Group` button.
    * This group should have read only permission.
2. Create new users by clicking on the `Admin` tab at the top navigation bar and then click the `Add new User` button.
    * User that owns the image: This user should have the User role and be in the `public` group.
    * Public user: This user should have the User role and be in the `public` group.
3. Be sure to remember the passwords of these users as these will be used later. The credentials of these users in the current installation of Omero can be obtained by contacting ANS IT.

### Enable the web domain url without the port 4080
When first setting up the Omero web application, the default url may be `<ip-address>:4080`. If you want to change this, you will need to run Caddy and use a reverse proxy.
1. The `Caddyfile` configuration file is in the GitHub repository and must be moved to be in the same directory as the `docker-compose.yml` file. 
2. View the comments in the `Caddyfile` and `docker-compose.yml` file and add the appropriate configurations for your server.
3. Shut down the Docker containers and start them again for the changes to take effect.
4. You will know if the changes worked when you go to the url `https://<web-domain>`, replacing `<web-domain>` with the domain you provided in the configuration, and you see the login page or the public user's dashboard.

### Setting up the Conversion Pipeline
1. (#TODO)

### Setting up the Import Pipeline
1. Create a daemon service file `/etc/systemd/system/import.service` using your favorite editor (must use sudo)
2. Add the following lines to the file:
```
[Unit]
Description=Omero Import Daemon

[Service]
ExecStart=</path/to/miniconda>/envs/ome/bin/python3 -u </path/to/import_monitor.py> -u <username> -w <password> </path/to/mount/with/converted/images> -v -l </path/to/your/import/logs/file>
Restart=always

[Install]
WantedBy=multi-user.target
```
* `</path/to/miniconda>` - path to your miniconda instance
* `</path/to/import_monitor.py>` - path to your import_monitor.py script (found in the GitHub repository)
* `<username>` - Omero username of the user that will own the images
* `<password>` - password of the Omero user
* `</path/to/mount/with/converted/images>` - path to the mounted directory with the converted images from the conversion server
* `</path/to/your/import/logs/file>` - path to the import logs file that will store the logs for the imports 

3. Start the daemon service by running `sudo systemctl start import`

4. You can check the status of the daemon service by running `sudo systemctl status import`

5. You can view the import logs by looking at the log file, which you provided as an argument in the import service file.

6. You can shut down the daemon service by running `sudo systemctl stop import`

7. You will need to enable the daemon service on boot by running `sudo systemctl enable import.service`

8. After setting up the daemon service, you need to set up the root cronjob to restart the daemon service every day and run the reimport script just in case the daemon service gets hung up for whatever reason. 
    * Run the command `sudo crontab -e` to create a root cronjob
    * Add the following line to the cronjob file: \
    `0 5 * * * /usr/bin/systemctl restart import && </path/to/reimport_images_run.sh> >> </path/to/reimport/logs/file> 2>&1`
        * `</path/to/reimport_images_run.sh>` - path to the reimport_images_run.sh file in the server. This file can be found in the GitHub repository. Follow the instructions in the file to customize it to your needs.
        * `</path/to/reimport/logs/file>` - path to the reimport logs file that will store the logs for the images that were reimported due to failure 
    * Make sure that the `reimport_images_run.sh` file is executable and the `reimport_images.py` file is in the Omero docker container via a mount declared in `docker-compose.yml`