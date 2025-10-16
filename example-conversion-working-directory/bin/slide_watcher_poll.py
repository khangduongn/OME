import csv
import time
import os
import subprocess
import logging
import shutil
import sys
from conversion_automated import convert_slide

import yaml
from pathlib import Path
from typing import Dict

logging.getLogger('watchdog').setLevel(logging.WARNING)

REQUIRED_TAGS = {"input", "recycle", "output", "failure", "staging"}



class DirectoryProcessor:
    def __init__(self, input_directory, recycle_directory, output_directory, failure_directory, staging_directory, check_interval=60):
        self.input_directory = input_directory
        self.recycle_directory = recycle_directory
        self.output_directory = output_directory
        self.failure_directory = failure_directory
        self.staging_directory = staging_directory
        self.check_interval = check_interval
        self.is_processing = False

    def start(self):
        """Start the periodic directory checking loop."""
        print("Checking for new directories...")
        while True:
            if not self.is_processing:
                self.process_existing_slides()
            time.sleep(self.check_interval)

    def process_existing_slides(self):
        """Process all slides in the directories."""
        self.is_processing = True
        try:
            for slide_name in os.listdir(self.input_directory):
                slide_path = os.path.join(self.input_directory, slide_name)
                if os.path.isdir(slide_path) and self.is_top_level_directory(slide_path):
                    self.handle_new_slide(slide_path)
                    print("Checking for new directories...")
        finally:
            self.is_processing = False

    def is_top_level_directory(self, slide_path):
        """Check if the directory is a top-level directory within the watched directory."""
        parent_directory = os.path.dirname(slide_path)
        return parent_directory == self.input_directory

    def handle_new_slide(self, slide_path):
        """Process a new slide directory."""
        print(f"Waiting for slide directory to stabilize: {slide_path}")
        self.wait_for_stability(slide_path)

        print("Checking available storage...")
        self.wait_for_sufficient_storage(slide_path)

        csv_file = os.path.join(self.failure_directory, 'flagged_images.csv')

        if self.validate_slide(slide_path, csv_file):
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
                stable_time = 0

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

    def validate_slide(self, slide_path, csv_file):
        slide_name = os.path.basename(slide_path)
        expected_subdir = os.path.join(slide_path, slide_name)

        if not os.path.isdir(expected_subdir):
            error_message = f"Subdirectory with the same name as the slide does not exist in {slide_path}"
            print(error_message)
            self.log_error(csv_file, slide_path, error_message)
            return False

        xyz_file_path = os.path.join(expected_subdir, 'XYZPositions.txt')
        if not os.path.isfile(xyz_file_path):
            error_message = f"File 'XYZPositions.txt' not found in subdirectory {expected_subdir}"
            print(error_message)
            self.log_error(csv_file, slide_path, error_message)
            return False

        if os.path.exists(os.path.join(self.recycle_directory, slide_name)):
            error_message = f"Slide {slide_name} is located in the recycle directory {self.recycle_directory}"
            print(error_message)
            self.log_error(csv_file, slide_path, error_message)
            return False

        slide_file_with_ext = f"{slide_name}.ome.tiff"
        output_path = os.path.join(self.output_directory, slide_file_with_ext)
        if os.path.isfile(output_path):
            error_message = f"Slide {slide_file_with_ext} already exists in output ({self.output_directory})"
            print(error_message)
            self.log_error(csv_file, slide_path, error_message)
            return False

        print("Slide meets criteria for processing")
        return True

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
            self.move_to_failures(slide_path)

    def move_to_failures(self, slide_path):
        slide_name = os.path.basename(slide_path)
        destination = os.path.join(self.failure_directory, slide_name)

        if os.path.exists(destination):
            counter = 1
            while os.path.exists(destination):
                destination = os.path.join(self.failure_directory, f"{slide_name}({counter})")
                counter += 1

        shutil.move(slide_path, destination)
        print(f"Moved {slide_path} to {destination}")

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

    def log_error(self, csv_file, slide_path, error_message):
        with open(csv_file, mode='a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([slide_path, error_message])

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

def load_folder_config(config_path) -> Dict[str, Path]:
    """
    Reads a YAML file with a top-level 'folders:' mapping of tags to paths,
    validates required tags, ensures each path exists, and returns
    a dict[tag] = Path.
    """
    config_path = Path(config_path)
    if not config_path.is_file():
        raise FileNotFoundError(f"Config not found: {config_path}")

    with config_path.open() as f:
        cfg = yaml.safe_load(f)

    folders = cfg.get("folders")
    if not isinstance(folders, dict):
        raise ValueError(f"'folders' must be a mapping in {config_path}")

    missing = REQUIRED_TAGS - set(folders)
    if missing:
        raise KeyError(f"Missing folder tags in config: {missing}")

    result: Dict[str, Path] = {}
    for tag, p in folders.items():
        if tag not in REQUIRED_TAGS:
            raise KeyError(f"Unexpected folder tag: {tag}")
        path = Path(p)
        if not path.exists():
            raise FileNotFoundError(f"Folder for '{tag}' does not exist: {path}")
        result[tag] = p

    return result

if __name__ == "__main__":

    script_path = Path(__file__).resolve()
    app_root    = script_path.parent.parent
    config_file = app_root / "config" / "conversion_conf.yml"
    directories = load_folder_config(config_file)
    
    processor = DirectoryProcessor(
        input_directory=directories["input"],
        recycle_directory=directories["recycle"],
        output_directory=directories["output"],
        failure_directory=directories["failure"],
        staging_directory=directories["staging"]
    )
    processor.start()
    
    
    
