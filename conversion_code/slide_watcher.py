import csv
import time
import os
import subprocess
import logging
import shutil

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from conversion_automated import convert_slide

logging.getLogger('watchdog').setLevel(logging.WARNING)


class DirectoryEventHandler(FileSystemEventHandler):
    def __init__(self, input_directory, recycle_directory, output_directory, failure_directory, staging_directory):
        super().__init__()
        self.input_directory = input_directory
        self.recycle_directory = recycle_directory
        self.output_directory = output_directory
        self.failure_directory = failure_directory
        self.staging_directory = staging_directory
        self.process_existing_slides()  # Only called once during initialization

    def process_existing_slides(self):
        """Process all slides in the directories when the script is initially run."""
        for slide_name in os.listdir(self.input_directory):
            slide_path = os.path.join(self.input_directory, slide_name)
            if os.path.isdir(slide_path) and self.is_top_level_directory(slide_path):
                self.handle_new_slide(slide_path)

    def on_created(self, event):
        """Handle newly created directories."""
        if event.is_directory and self.is_top_level_directory(event.src_path):
            print(f"New slide directory detected: {event.src_path}")
            self.handle_new_slide(event.src_path)

    def is_top_level_directory(self, slide_path):
        """Check if the directory is a top-level directory within the watched directory."""
        parent_directory = os.path.dirname(slide_path)
        return parent_directory == self.input_directory

    def handle_new_slide(self, slide_path):
        """Process a new slide directory."""
        print(f"Waiting for slide directory to stabilize: {slide_path}")
        self.wait_for_stability(slide_path)

        print(f"Checking available storage")
        self.wait_for_sufficient_storage(slide_path)

        # Determine the failure directory to locate the `flagged_images.csv` file
        # parent_directory = os.path.dirname(slide_path)
        csv_file = os.path.join(self.failure_directory, 'flagged_images.csv')

        # Perform validation checks after the slide directory stabilizes
        if self.validate_slide(slide_path, csv_file):
            # Call the standalone code after validation
            self.process_slide(slide_path, csv_file)
        else:
            self.move_to_failures(slide_path)

    def wait_for_stability(self, slide_path, check_interval=60, stability_duration=120):
        stable_time = 0
        previous_size = -1

        while stable_time < stability_duration:
            current_size = self.get_slide_size_du(slide_path)
            if current_size == previous_size:
                stable_time += check_interval
            else:
                stable_time = 0  # Reset the stable time if any change is detected

            previous_size = current_size
            time.sleep(check_interval)

    def get_slide_size_du(self, slide_path):
        result = subprocess.run(['du', '-sb', slide_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode == 0:
            return int(result.stdout.split()[0])
        else:
            error_message = f"Error running du command: {result.stderr.decode().strip()}"
            print(error_message)
            return -1

    def log_error(self, csv_file, slide_path, error_message):
        # Log the error by appending to the `flagged_images.csv` file
        with open(csv_file, mode='a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([slide_path, error_message])

    def validate_slide(self, slide_path, csv_file):
        slide_name = os.path.basename(slide_path)
        expected_subdir = os.path.join(slide_path, slide_name)

        # Condition 1: Check if subdirectory with the same name as the slide exists
        if not os.path.isdir(expected_subdir):
            error_message = f"Subdirectory with the same name as the slide does not exist in {slide_path}"
            print(error_message)
            self.log_error(csv_file, slide_path, error_message)
            return False

        # Condition 2: Check if XYZPositions.txt exists in the expected subdirectory
        xyz_file_path = os.path.join(expected_subdir, 'XYZPositions.txt')
        if not os.path.isfile(xyz_file_path):
            error_message = f"File 'XYZPositions.txt' not found in subdirectory {expected_subdir}"
            print(error_message)
            self.log_error(csv_file, slide_path, error_message)
            return False

        # Condition 3: Check if slide_name is in the recycle directory
        if os.path.exists(os.path.join(self.recycle_directory, slide_name)):
            error_message = f"Slide {slide_name} is located in the recycle directory {self.recycle_directory}"
            print(error_message)
            self.log_error(csv_file, slide_path, error_message)
            return False

        # Condition 4: Check if a file with slide_name.ome.tiff exists in output 
        slide_file_with_ext = f"{slide_name}.ome.tiff"
        output_path = os.path.join(self.output_directory, slide_file_with_ext)
        if os.path.isfile(output_path):
            error_message = f"Slide {slide_file_with_ext} already exists in output ({self.output_directory})"
            print(error_message)
            self.log_error(csv_file, slide_path, error_message)
            return False

        print("Slide meets criteria for processing")
        return True
    
    def move_to_failures(self, slide_path):
        slide_name = os.path.basename(slide_path)
        destination = os.path.join(self.failure_directory, slide_name)

        # Check if the destination folder already exists, and append a number if it does
        if os.path.exists(destination):
            counter = 1
            while os.path.exists(destination):
                destination = os.path.join(self.failure_directory, f"{slide_name}({counter})")
                counter += 1

        # Move the slide to the final destination folder in the failures directory
        shutil.move(slide_path, destination)
        print(f"Moved {slide_path} to {destination}")

    def process_slide(self, slide_path, csv_file):
        try:
            params = StitchParams(
                input_dir=slide_path,
                output_dir=self.output_directory, 
                staging_dir=self.staging_directory,
                failure_dir=self.failure_directory,
                tile_size=[256, 256],
                compression='JPEG',
                quality=80,
                verbose=True,
                debug=False,  
                pyramid_resolutions=3,
                pyramid_scale=4,
                bigtiff=True
            )

            return_val = convert_slide(params)

            if return_val == 0:
                slide_name = os.path.basename(slide_path)
                shutil.move(slide_path, self.recycle_directory)                
            else:
                self.move_to_failures(slide_path)          

        except Exception as e:
            error_message = f"Error processing slide {slide_path}: {e}"
            print(error_message)
            shutil.move(slide_path, self.failure_directory)
            self.log_error(csv_file, slide_path, error_message)

    def wait_for_sufficient_storage(self, slide_path):
        slide_size = self.get_slide_size_du(slide_path)
        if slide_size == -1:
            print(f"Could not determine size for slide at: {slide_path}")
            return False
        
        required_space_output = slide_size / 3
        required_space_failure = slide_size * 2
        required_space_staging = slide_size * 5

        wait_message_printed = False

        while True:
            # Check space in failure_directory and output_directory
            failure_dir_space = shutil.disk_usage(self.failure_directory).free
            output_dir_space = shutil.disk_usage(self.output_directory).free
            staging_dir_space = shutil.disk_usage(self.staging_directory).free

            # If both directories have sufficient space, break out of the loop
            if failure_dir_space >= required_space_failure and output_dir_space >= required_space_output and staging_dir_space >= required_space_staging:
                if wait_message_printed:
                    print("Sufficient storage is now available in both directories.")
                return True

            # Print the wait message once if space is insufficient
            if not wait_message_printed:
                def format_space(bytes_value):
                    if bytes_value >= 1024 ** 3:  # Convert to GB if >= 1 GB
                        return f"{bytes_value / (1024 ** 3):.2f} GB"
                    elif bytes_value >= 1024 ** 2:  # Convert to MB if >= 1 MB
                        return f"{bytes_value / (1024 ** 2):.2f} MB"
                    elif bytes_value >= 1024:  # Convert to KB if >= 1 KB
                        return f"{bytes_value / 1024:.2f} KB"
                    else:  # Less than 1 KB, keep it in bytes
                        return f"{bytes_value} bytes"
                if failure_dir_space < required_space_failure:
                    required_space = required_space_failure - failure_dir_space
                    print(f"Waiting for space in failure directory: {self.failure_directory}. Required: {format_space(required_space)}.")
                if output_dir_space < required_space_output:
                    required_space = required_space_output - output_dir_space
                    print(f"Waiting for space in output directory: {self.output_directory}. Required: {format_space(required_space)}.")
                if staging_dir_space < required_space_staging:
                    required_space = required_space_staging - staging_dir_space
                    print(f"Waiting for space in staging directory: {self.staging_directory}. Required: {format_space(required_space)}.")
                wait_message_printed = True
            
            time.sleep(10)


class ConfigFileHandler(FileSystemEventHandler):
    def __init__(self, config_file, observer):
        self.config_file = config_file
        self.observer = observer
        self.current_directories = set()

    def on_modified(self, event):
        if event.src_path == self.config_file:
            print(f"Config file {self.config_file} modified. Reloading directories...")
            self.load_directories()

    def load_directories(self):
        directories_set = set()  # To track all unique directories
        with open(self.config_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                input_dir = row['Input'].strip()
                recycle_dir = row['Recycle'].strip()
                output_dir = row['Output'].strip()
                failure_dir = row['Failure'].strip()
                staging_dir = row['Staging'].strip()

                if not (os.path.isdir(input_dir) and os.path.isdir(recycle_dir) and os.path.isdir(output_dir) and os.path.isdir(failure_dir) and os.path.isdir(staging_dir)):
                    print(f"Skipping invalid directories: {input_dir}, {recycle_dir}, {output_dir}, {failure_dir}, {staging_dir}")
                    continue

                if input_dir in directories_set or recycle_dir in directories_set or output_dir in directories_set or failure_dir in directories_set or staging_dir in directories_set:
                    print(f"Skipping duplicate directories: {input_dir}, {recycle_dir}, {output_dir}, {failure_dir}, {staging_dir}")
                    continue

                directories_set.update([input_dir, recycle_dir, output_dir, failure_dir, staging_dir])

                print(f"Starting watch on directory: {input_dir}")
                event_handler = DirectoryEventHandler(input_dir, recycle_dir, output_dir, failure_dir, staging_dir)
                self.observer.schedule(event_handler, input_dir, recursive=False)

        self.current_directories.update(directories_set)


def watch_directories(config_file):
    observer = Observer()

    # Watch the config file for changes
    config_event_handler = ConfigFileHandler(config_file, observer)
    observer.schedule(config_event_handler, path=os.path.dirname(config_file) or '.', recursive=False)
    config_event_handler.load_directories()  # Initial loading of directories

    observer.start()
    print(f"Watching directories listed in: {config_file}")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

class StitchParams:
    def __init__(self, input_dir, output_dir, staging_dir, failure_dir, tile_size, compression, quality, verbose, debug, pyramid_resolutions, pyramid_scale, bigtiff):
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.staging_dir = staging_dir
        self.failure_dir = failure_dir
        self.tile_size = tile_size
        self.compression = compression
        self.quality = quality
        self.verbose = verbose
        self.debug = debug
        self.pyramid_resolutions = pyramid_resolutions
        self.pyramid_scale = pyramid_scale
        self.bigtiff = bigtiff

if __name__ == "__main__":
    # Replace '/path/to/directories_to_watch.csv' with the path to your configuration CSV file
    config_file = "/path/to/directories_to_watch.csv"
    if os.path.isfile(config_file):
        watch_directories(config_file)
    else:
        print(f"Config file {config_file} does not exist.")
