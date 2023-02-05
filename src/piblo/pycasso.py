#!/usr/bin/python3
# -*- coding:utf-8 -*-
# Main pycasso class to run

import argparse
import logging
import os
import random
import warnings

import numpy
from PIL import Image, ImageDraw, ImageFont, PngImagePlugin
from omni_epd import displayfactory, EPDNotFoundError

from piblo.config_wrapper import Configs
from piblo.constants import ProvidersConst, ConfigConst, PropertiesConst, PromptModeConst, ImageConst, AutomaticConst, \
    IconFileConst
from piblo.file_operations import FileOperations
from piblo.image_functions import ImageFunctions
from piblo.provider import StabilityProvider, DalleProvider, AutomaticProvider


# noinspection PyTypeChecker
class Pycasso:
    """
    Object used to run pycasso

    Attributes
    ----------

    Methods
    -------
    parse_args()
        Function parses arguments provided via command line. Returns the parser object.

    load_config()
        Loads config from file provided to it or sets defaults

    display_image_on_EPD(display_image, epd):
        Displays PIL image object 'display_image' on omni_epd object 'epd'

    save_image(prompt, image, metadata, path="", extension):
        Saves a PIL image 'image' with 'extension' (default png) based on string 'prompt', with metadata object
        'metadata'

    load_external_image(location, width, height, preamble_regex, artist_regex, remove_text, parse_text, extension)
        Loads a random external image previously generated by pycasso within file path string 'location' and with
        'extension' (default png). Will be resized to pixel size 'width' and 'height'. 'preamble regex' is text to be
        removed from the start of the filename before the title. 'artist_regex' is text to be removed from between the
        title and artist. 'remove_text' is a list of text items to be found and removed wherever occurring in filename.
        returns PIL image object, title string and artist string

    load_historic_image(location, extension):
        Loads a random historic image previously generated by pycasso within file path string 'location' and with
        'extension' (default png)
        returns PIL image object, title string and artist string

    load_stability_image(prompt, width, height, stability_key=None):
        Uses Stable Diffusion API to request an image based on 'prompt' text, of pixel dimensions 'width' and 'height'
        API key should be provided in 'stability_key'
        returns PIL image object

    load_automatic_image(prompt, width, height):
        Uses local Automatic111 Stable Diffusion API to request an image based on 'prompt' text, of pixel dimensions
        'width' and 'height'
        returns PIL image object

    load_dalle_image(prompt, width, height, infill=False, dalle_key=None):
        Uses Dalle API to request an image based on 'prompt' text, of pixel dimensions 'width' and 'height'.
        If infill set to 'True' it will make a second request to fill out the screen to avoid gaps or ugly cropping
        API key should be provided in 'dalle_key'
        returns PIL image object

    parse_multiple_brackets(text, bracket_pairs):
        Takes 'text' and applies parsing based on all 2 string bracket strings in 'bracket_pairs' list, sequentially.
        returns updated text

    prep_prompt_text(self, prompt_mode):
        Function to prepare prompt text based on current state of the class. Prompt mode to select which generation mode
        to be used.
        returns prompt string, PNG metadata object, artist string and title string

    prep_subject_artist_prompt(artists_file, subjects_file, preamble, connector, postscript)
        Prepares a prompt mode using subject and artist. 'artists_file' is the location of the text file containing
        artists, 'subjects_file' is the location of the text file containing subjects, 'preamble' is a string to place
        at the start of the prompt, 'connector' is a string to place between artist and subject and 'postscript' is a
        string to place at the end of the prompt.
        return prompt string, artist string and title string

    prep_normal_prompt(prompts_file, preamble, postscript)
        Prepares a prompt mode using a prompt file. 'prompts_file' is the location of the text file containing prompts,
        'preamble' is a string to place at the start of the prompt, and 'postscript' is a string to place at the end of
        the prompt.
        return prompt string and title string

    get_random_provider_mode()
        returns a random provider mode based on the current set available to pycasso

    add_text_to_image(draw, font_file, image_height, epd_width, title_text, artist_text, title_location,
                      artist_location, padding, opacity, title_size, artist_size, box_to_floor, box_to_edge, crop_left,
                      crop_right)
        Adds text via a 'draw' object passed to the function. 'font_file' specifies a file location of a true type font.
        image_height, is the height of the actual image retrieved from the provider or file, epd_width is the width of
        the epd screen. 'title_text' and 'artist_text' are strings that provide the selected artist and title
        respectively. 'title_location' and 'artist_location' provide the location in pixels from the bottom of the
        image/display to place the text. 'padding' is how much additional space the text box takes in pixels from the
        normal area of the text. 'opacity' is a 0-255 integer value of opacity. 'title_size' and 'artist_size' are the
        text sizes of the title and artist respectively. 'box_to_floor' is a boolean flag to draw the text box to the
        bottom of the image or not. 'box_to_edge' is a boolean flag to draw the text box to the edges of the image or
        not. 'crop_left' and 'crop_right' are the cropped image coordinates to use if 'box to edge' is used. These do
        not need to be set if box_to_edge is false.

    run()
        Do pycasso
    """

    def __init__(self, config_path=None, file_path=os.getcwd(), charge_level=-1):
        self.file_path = file_path

        # Config Dictionary for omni-epd
        self.config_dict = {}

        # EPD
        self.epd = None

        # Image
        self.image_base = None

        # Prompt
        self.prompt = ""
        self.artist_text = ""
        self.title_text = ""
        self.metadata = None

        # Icon
        self.charge_level = charge_level
        self.icon_shape = None
        self.icons = []

        # Keys
        self.stability_key = None
        self.dalle_key = None

        # Args read
        self.args = self.parse_args()
        self.stability_key = self.args.stabilitykey
        self.dalle_key = self.args.dallekey
        if self.args.displayshape is not None:
            self.icon_shape = self.args.displayshape

        # Load config or set defaults
        self.config = self.load_config(config_path)

        if self.args.savekeys:
            if self.stability_key is not None:
                StabilityProvider.add_secret(self.stability_key, self.config.use_keychain, self.config.credential_path)
            if self.dalle_key is not None:
                DalleProvider.add_secret(self.dalle_key, self.config.use_keychain, self.config.credential_path)

        return

    @staticmethod
    def parse_args():
        args = None
        try:
            parser = argparse.ArgumentParser(
                description="A program to request an image from preset APIs and apply them to an"
                            " epaper screen through a raspberry pi unit")
            parser.add_argument("--configpath",
                                dest="configpath",
                                type=str,
                                help="Path to .config file. Default: \'.config\'")
            parser.add_argument("--stabilitykey",
                                dest="stabilitykey",
                                type=str,
                                help="Stable Diffusion API Key")
            parser.add_argument("--dallekey",
                                dest="dallekey",
                                type=str,
                                help="Dalle API Key")
            parser.add_argument("--savekeys",
                                dest="savekeys",
                                action="store_const",
                                const=1,
                                default=0,
                                help="Use this flag to save any keys provided to system keyring")
            parser.add_argument("--norun",
                                dest="norun",
                                action="store_const",
                                const=1,
                                default=0,
                                help="This flag ends the program before starting the main functionality of pycasso."
                                     "This will not fetch images or update the epaper screen")
            parser.add_argument("--displayshape",
                                dest="displayshape",
                                type=int,
                                help="Displays a shape in the top left corner of the epd. Good for providing visual"
                                     "information while using a mostly disconnected headless setup."
                                     "\n0 - Square\n1 - Cross\n2 - Triangle\n3 - Circle")

            args, unknown = parser.parse_known_args()

            if len(unknown) > 0:
                logging.warning(f"Ignoring unknown argument(s): {unknown}")

        except argparse.ArgumentError as e:
            logging.error(e)
            exit()

        except BaseException as e:
            logging.error(e)
            exit()

        return args

    def load_config(self, config_path=None):
        # Loads config from file provided to it or sets defaults
        config = None

        try:
            if config_path is None:
                config_path = ConfigConst.CONFIG_PATH.value
                if self.args is not None:
                    if self.args.configpath is not None:
                        config_path = self.args.configpath

            config = Configs(config_path=config_path, path=self.file_path)

            self.config_dict = config.read_config()

            log_file = ConfigConst.LOGGING_FILE.value

            # Set up logging
            if config.log_file is not None and config.log_file != "":
                log_file = os.path.join(self.file_path, config.log_file)

            logging.basicConfig(level=config.log_level, filename=log_file,
                                format='%(asctime)s %(levelname)-8s %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
            logging.info("Config loaded")

        except IOError as e:
            logging.error(e)

        except KeyboardInterrupt:
            logging.info("ctrl + c:")
            exit()

        return config

    @staticmethod
    def display_image_on_epd(display_image, epd):
        logging.info("Prepare epaper")
        epd.prepare()

        epd.display(display_image)

        logging.info("Send epaper to sleep")
        epd.close()
        return

    @staticmethod
    def load_test_image(width, height, title_text="", artist_text="",
                        image_path=ProvidersConst.TEST_FILE.value,
                        resize_external=ConfigConst.FILE_RESIZE_EXTERNAL.value):
        # Get test image
        image_base = Image.open(image_path)

        text = title_text

        # Add text
        artist_text = f"I could have been '{text}'"
        title_text = "It Works! Explore .config to customise!"

        # Resize to thumbnail size based on epd resolution depending on if option selected
        epd_res = (width, height)
        img_res = (image_base.width, image_base.height)
        epd_res = ImageFunctions.min_possible_tup(epd_res, img_res)
        image_base.thumbnail(epd_res)

        return image_base, title_text, artist_text

    @staticmethod
    def load_external_image(location, width, height, preamble_regex=ConfigConst.TEXT_PREAMBLE_REGEX.value,
                            artist_regex=ConfigConst.TEXT_ARTIST_REGEX,
                            remove_text=ConfigConst.TEXT_REMOVE_TEXT_LIST.value,
                            parse_text=ConfigConst.TEXT_PARSE_FILE_TEXT.value,
                            extension=ConfigConst.FILE_IMAGE_FORMAT.value,
                            resize_external=ConfigConst.FILE_RESIZE_EXTERNAL.value):
        image_directory = location
        if not os.path.exists(image_directory):
            warnings.warn("External image directory path does not exist: '" + image_directory + "'")
            exit()

        # Get random image from folder
        file = FileOperations(image_directory)
        image_path = file.get_random_file_of_type(extension)
        image_base = Image.open(image_path)

        # Add text to via parsing if necessary
        image_name = os.path.basename(image_path)
        title_text = image_name
        artist_text = None

        if parse_text:
            title_text, artist_text = FileOperations.get_title_and_artist(image_name,
                                                                          preamble_regex,
                                                                          artist_regex,
                                                                          extension)
            title_text = FileOperations.remove_text(title_text, remove_text)
            artist_text = FileOperations.remove_text(artist_text, remove_text)
            title_text = title_text.title()
            artist_text = artist_text.title()

        # Resize to thumbnail size based on epd resolution depending on if option selected
        epd_res = (width, height)
        if not resize_external:
            epd_res = ImageFunctions.max_tup(epd_res)
        image_base.thumbnail(epd_res)

        return image_base, title_text, artist_text

    @staticmethod
    def load_historic_image(location, extension=ConfigConst.FILE_IMAGE_FORMAT.value):
        image_directory = location
        if not os.path.exists(image_directory):
            warnings.warn(f"Historic image directory path does not exist: '{image_directory}'")
            exit()

        # Get random image from folder
        file = FileOperations(image_directory)
        image_path = file.get_random_file_of_type(extension)
        image_base = Image.open(image_path)
        image_name = os.path.basename(image_path)
        title_text = image_name
        artist_text = None

        # Get and apply metadata if it exists
        metadata = image_base.text
        if PropertiesConst.TITLE.value in metadata.keys():
            title_text = metadata[PropertiesConst.TITLE.value]
        elif PropertiesConst.PROMPT.value in metadata.keys():
            title_text = metadata[PropertiesConst.PROMPT.value]
        if PropertiesConst.ARTIST.value in metadata.keys():
            artist_text = metadata[PropertiesConst.ARTIST.value]
        return image_base, title_text, artist_text

    @staticmethod
    def load_stability_image(prompt, width, height, stability_key=None):
        logging.info("Loading Stability API")
        if stability_key is None:
            stability_provider = StabilityProvider()
        else:
            stability_provider = StabilityProvider(key=stability_key)

        logging.info("Getting Image")
        image = stability_provider.get_image_from_string(prompt, height, width)
        return image

    @staticmethod
    def load_dalle_image(prompt, width, height, infill=ConfigConst.GENERATION_INFILL.value,
                         infill_percent=ConfigConst.GENERATION_INFILL_PERCENT.value, dalle_key=None):
        logging.info("Loading Dalle API")
        if dalle_key is None:
            dalle_provider = DalleProvider()
        else:
            dalle_provider = DalleProvider(key=dalle_key)

        logging.info("Getting Image")
        image_base = dalle_provider.get_image_from_string(prompt, height, width)

        # Use infill to fill in sides of image instead of cropping
        if infill:
            image_base = dalle_provider.infill_image_from_image(prompt, image_base, infill_percent)

        return image_base

    @staticmethod
    def load_automatic_image(prompt, width, height, host=AutomaticConst.DEFAULT_HOST.value,
                             port=AutomaticConst.DEFAULT_PORT.value):
        logging.info("Loading Automatic API")
        automatic_provider = AutomaticProvider(host=host, port=port)

        logging.info("Getting Image")
        image = automatic_provider.get_image_from_string(prompt, height, width)
        return image

    def prep_prompt_text(self, prompt_mode=PromptModeConst.PROMPT.value):
        # Build prompt, add metadata as we go
        self.metadata = PngImagePlugin.PngInfo()
        artist_text = None

        if prompt_mode == PromptModeConst.RANDOM.value:
            # Pick random type of building
            random.seed()
            prompt_mode = random.randint(1, ConfigConst.PROMPT_MODES_COUNT.value)

        if prompt_mode == PromptModeConst.SUBJECT_ARTIST.value:
            # Build prompt from artist/subject
            prompt_gen = self.prep_subject_artist_prompt(self.config.artists_file, self.config.subjects_file,
                                                         self.config.prompt_preamble, self.config.prompt_connector,
                                                         self.config.prompt_postscript, self.config.parse_brackets,
                                                         self.config.parse_random_text)
            self.prompt, self.artist_text, self.title_text = prompt_gen
            self.metadata.add_text(PropertiesConst.ARTIST.value, self.artist_text)
            self.metadata.add_text(PropertiesConst.TITLE.value, self.title_text)

        elif prompt_mode == PromptModeConst.PROMPT.value:
            # Build prompt from prompt file
            prompt_gen = self.prep_normal_prompt(self.config.prompts_file, self.config.prompt_preamble,
                                                 self.config.prompt_postscript, self.config.parse_brackets,
                                                 self.config.parse_random_text)
            self.prompt, self.title_text = prompt_gen
            artist_text = ""
        else:
            warnings.warn("Invalid prompt mode chosen. Using default prompt mode.")
            # Build prompt from prompt file
            prompt_gen = self.prep_normal_prompt(self.config.prompts_file, self.config.prompt_preamble,
                                                 self.config.prompt_postscript)
            self.prompt, self.title_text = prompt_gen

        self.metadata.add_text(PropertiesConst.PROMPT.value, self.prompt)
        return self.prompt, self.metadata, self.artist_text, self.title_text

    @staticmethod
    def parse_multiple_brackets(text, bracket_pairs=ConfigConst.TEXT_PARSE_BRACKETS_LIST.value):
        pairs = bracket_pairs.copy()
        pairs.reverse()
        for brackets in pairs:
            text = FileOperations.parse_text(text, brackets[0], brackets[1])
        return text

    @staticmethod
    def prep_subject_artist_prompt(artists_file, subjects_file, preamble=ConfigConst.PROMPT_PREAMBLE.value,
                                   connector=ConfigConst.PROMPT_CONNECTOR.value,
                                   postscript=ConfigConst.PROMPT_POSTSCRIPT.value,
                                   brackets=ConfigConst.TEXT_PARSE_BRACKETS_LIST.value,
                                   parse=ConfigConst.TEXT_PARSE_RANDOM_TEXT):
        artist_text = FileOperations.get_random_line(artists_file)
        title_text = FileOperations.get_random_line(subjects_file)

        if parse:
            artist_text = Pycasso.parse_multiple_brackets(artist_text, brackets)
            title_text = Pycasso.parse_multiple_brackets(title_text, brackets)
            preamble = Pycasso.parse_multiple_brackets(preamble, brackets)
            connector = Pycasso.parse_multiple_brackets(connector, brackets)
            postscript = Pycasso.parse_multiple_brackets(postscript, brackets)

        prompt = (preamble + title_text + connector + artist_text + postscript)
        return prompt, artist_text, title_text

    @staticmethod
    def prep_normal_prompt(prompts_file, preamble=ConfigConst.PROMPT_PREAMBLE.value,
                           postscript=ConfigConst.PROMPT_POSTSCRIPT.value,
                           brackets=ConfigConst.TEXT_PARSE_BRACKETS_LIST.value,
                           parse=ConfigConst.TEXT_PARSE_RANDOM_TEXT):
        title_text = FileOperations.get_random_line(prompts_file)

        if parse:
            title_text = Pycasso.parse_multiple_brackets(title_text, brackets)
            preamble = Pycasso.parse_multiple_brackets(preamble, brackets)
            postscript = Pycasso.parse_multiple_brackets(postscript, brackets)

        prompt = preamble + title_text + postscript
        return prompt, title_text

    @staticmethod
    def save_image(prompt, image, metadata, path="", extension=ConfigConst.FILE_IMAGE_FORMAT.value):
        image_name = PropertiesConst.FILE_PREAMBLE.value + prompt + "." + extension
        save_path = os.path.join(path, image_name)
        logging.info(f"Saving image as {save_path}")

        # Save the image
        image.save(save_path, pnginfo=metadata)
        return

    def get_random_provider_mode(self):
        provider_types = [
            ProvidersConst.EXTERNAL.value,
            ProvidersConst.HISTORIC.value,
            ProvidersConst.STABLE.value,
            ProvidersConst.DALLE.value,
            ProvidersConst.AUTOMATIC.value
        ]

        provider_weights = (
            self.config.external_amount,
            self.config.historic_amount,
            self.config.stability_amount,
            self.config.dalle_amount,
            self.config.automatic_amount
        )

        # If no weights provided, return test provider
        total_amounts = 0
        for i in provider_weights:
            total_amounts += i
        if total_amounts <= 0:
            logging.info("No provider weights used. Returning test mode.")
            return ProvidersConst.TEST.value
        # Pick random provider based on weight
        random.seed()
        provider_type = random.choices(provider_types, k=1, weights=provider_weights)[0]
        return provider_type

    def remove_provider_mode(self, mode):
        if mode == ProvidersConst.EXTERNAL.value:
            self.config.external_amount = 0
        elif mode == ProvidersConst.HISTORIC.value:
            self.config.historic_amount = 0
        elif mode == ProvidersConst.STABLE.value:
            self.config.stability_amount = 0
        elif mode == ProvidersConst.DALLE.value:
            self.config.dalle_amount = 0
        elif mode == ProvidersConst.AUTOMATIC.value:
            self.config.automatic_amount = 0
        else:
            logging.warning(f"Tried to remove invalid mode {mode}.")
        return

    @staticmethod
    def add_text_to_image(draw, font_file, image_height, epd_width, title_text="", artist_text="",
                          title_location=ConfigConst.TEXT_TITLE_LOC.value,
                          artist_location=ConfigConst.TEXT_ARTIST_LOC.value,
                          padding=ConfigConst.TEXT_PADDING.value, opacity=ConfigConst.TEXT_OPACITY.value,
                          title_size=ConfigConst.TEXT_TITLE_SIZE.value, artist_size=ConfigConst.TEXT_ARTIST_SIZE.value,
                          box_to_floor=ConfigConst.TEXT_BOX_TO_FLOOR.value,
                          box_to_edge=ConfigConst.TEXT_BOX_TO_EDGE.value, crop_left=0, crop_right=0):
        if not os.path.exists(font_file):
            warnings.warn("Font file path does not exist: '" + font_file + "'. Setting default font.")
            title_font = ImageFont.load_default()
            artist_font = ImageFont.load_default()
        else:
            title_font = ImageFont.truetype(font_file, title_size)
            artist_font = ImageFont.truetype(font_file, artist_size)

        # proceed flag only to be set if set by prerequisite requirements
        proceed = False

        artist_box = (0, image_height, 0, image_height)
        title_box = artist_box

        if artist_text != "" and artist_text is not None:
            artist_box = draw.textbbox((epd_width / 2, image_height - artist_location),
                                       artist_text, font=artist_font, anchor="mb")
            proceed = True
        if title_text != "" and title_text is not None:
            title_box = draw.textbbox((epd_width / 2, image_height - title_location),
                                      title_text, font=title_font, anchor="mb")
            proceed = True

        draw_box = ImageFunctions.max_area([artist_box, title_box])
        draw_box = tuple(numpy.add(draw_box, (-padding, -padding, padding, padding)))

        # Modify depending on box type
        if box_to_floor:
            draw_box = ImageFunctions.set_tuple_bottom(draw_box, image_height)

        if box_to_edge:
            if crop_right == 0:
                # Set crop right to the width of the screen if it hasn't been set
                crop_right = epd_width
            draw_box = ImageFunctions.set_tuple_sides(draw_box, -crop_left, crop_right)

        # Only draw if we previously set proceed flag
        if proceed is True:
            draw.rectangle(draw_box, fill=(255, 255, 255, opacity))
            draw.text((epd_width / 2, image_height - artist_location), artist_text, font=artist_font,
                      anchor="mb", fill=0)
            draw.text((epd_width / 2, image_height - title_location), title_text, font=title_font,
                      anchor="mb", fill=0)
        return draw

    def get_image(self):
        provider_type = self.get_random_provider_mode()

        if provider_type == ProvidersConst.EXTERNAL.value:
            # External image load
            mode_list = self.load_external_image(self.config.external_image_location, self.epd.width, self.epd.height,
                                                 self.config.preamble_regex, self.config.artist_regex,
                                                 self.config.remove_text, self.config.parse_file_text,
                                                 self.config.image_format, self.config.resize_external)
            self.image_base, self.title_text, self.artist_text = mode_list

        elif provider_type == ProvidersConst.HISTORIC.value:
            # Historic image previously saved
            mode_list = self.load_historic_image(self.config.generated_image_location, self.config.image_format)
            self.image_base, self.title_text, self.artist_text = mode_list

        else:
            # Build prompt, get metadata
            self.prompt, self.metadata, self.artist_text, self.title_text = self.prep_prompt_text(self.config.prompt_mode)
            logging.info(f"Requesting \'{self.prompt}\'")

            # Pick between providers
            if provider_type == ProvidersConst.TEST.value and self.config.test_enabled is True:
                # Test run
                logging.info(
                    "Running test mode as no other provider selected. Configure providers in '.config' to enable "
                    "your preferred functionality. Set 'test_enabled = False' to prevent test mode from ever "
                    "running again."
                )
                self.image_base, self.title_text, self.artist_text = self.load_test_image(self.epd.width,
                                                                                          self.epd.height,
                                                                                          self.title_text,
                                                                                          self.artist_text)
                self.config.save_image = False

            elif provider_type == ProvidersConst.STABLE.value:
                # Stable Diffusion
                self.image_base = self.load_stability_image(self.prompt, self.epd.width, self.epd.height,
                                                            stability_key=self.stability_key)

            elif provider_type == ProvidersConst.DALLE.value:
                # Dalle
                self.image_base = self.load_dalle_image(self.prompt, self.epd.width, self.epd.height,
                                                        infill=self.config.infill, dalle_key=self.dalle_key)

            elif provider_type == ProvidersConst.AUTOMATIC.value:
                # Automatic
                self.image_base = self.load_automatic_image(self.prompt, self.epd.width, self.epd.height,
                                                            host=self.config.automatic_host,
                                                            port=self.config.automatic_port)

            else:
                # Invalid provider
                warnings.warn(f"Invalid provider option chosen: {provider_type}")
                exit()

            # Handle if image failed to load
            if self.image_base is None:
                logging.warning("Image failed to load. Please check providers.")
                return None, provider_type

            if self.config.save_image:
                self.save_image(self.prompt, self.image_base, self.metadata, self.config.generated_image_location)

        return self.image_base, provider_type

    def get_image_fallback_modes(self):
        error = True
        while error:
            error = False
            self.image_base, provider = self.get_image()
            if self.image_base is None:
                # If there's a failure to get the image
                error = True
                # Remove provider from possibilities
                logging.warning(f"Image failed to load on provider '{provider}'. Removing from circulation on this "
                                f"run.")
                self.remove_provider_mode(provider)
                self.add_exception_icon()
        return self.image_base

    def add_battery_icon(self, battery_percent):

        empty = range(0-20)
        low = range(21-40)
        half = range(41-60)
        good = range(61-80)
        full = range(81-100)

        if battery_percent in empty:
            battery_icon = IconFileConst.ICON_BATTERY_20.value
        elif battery_percent in low:
            battery_icon = IconFileConst.ICON_BATTERY_40.value
        elif battery_percent in half:
            battery_icon = IconFileConst.ICON_BATTERY_60.value
        elif battery_percent in good:
            battery_icon = IconFileConst.ICON_BATTERY_80.value
        elif battery_percent in full:
            battery_icon = IconFileConst.ICON_BATTERY_100.value
        else:
            # Somehow there's a battery read error
            battery_icon = IconFileConst.ICON_BATTERY_ERROR.value

        self.icons.append(battery_icon)
        return battery_icon

    def add_exception_icon(self):
        self.icons.append(IconFileConst.ICON_EXCEPTION.value)
        return

    def run(self):
        logging.info("pycasso has begun")

        try:
            self.epd = displayfactory.load_display_driver(self.config.display_type, self.config_dict)
            # If display is mock, apply height and width to it
            if self.config.display_type == ConfigConst.DISPLAY_TYPE.value:
                self.epd.width = self.config.test_epd_width
                self.epd.height = self.config.test_epd_height

        except EPDNotFoundError:
            logging.error(f"Couldn't find {self.config.display_type}")
            exit()

        except KeyboardInterrupt:
            logging.info("ctrl + c:")
            exit()

        except BaseException as e:
            logging.error(e)
            exit()

        if self.args.norun:
            logging.info("--norun option used, closing pycasso without running")
            exit()

        try:
            self.get_image_fallback_modes()

            if self.image_base is None:
                logging.error("Image failed to load. Please check providers or folders. Exiting pycasso.")
                exit()

            # Make sure image is correct size and centered after thumbnail set
            # Define locations and crop settings
            image_crop = ImageFunctions.get_crop_size(self.image_base.width, self.image_base.height, self.epd.width,
                                                      self.epd.height)
            crop_left = image_crop[0]
            crop_right = image_crop[2]

            # Crop and prepare image
            self.image_base = self.image_base.crop(image_crop)
            if self.image_base.mode not in ImageConst.SUPPORTED_MODES.value:
                self.image_base = self.image_base.convert(ImageConst.CONVERT_MODE.value)

            # Show battery icon if relevant
            if self.config.show_battery_icon:
                self.add_battery_icon(self.charge_level)

            # Draw icons
            self.image_base = ImageFunctions.draw_icons(self.image_base, self.icons, icon_path=self.config.icon_path,
                                                        icon_color=self.config.icon_color,
                                                        icon_location=self.config.icon_corner,
                                                        icon_padding=self.config.icon_padding,
                                                        icon_size=self.config.icon_size, icon_gap=self.config.icon_gap,
                                                        icon_opacity=self.config.icon_opacity)

            draw = ImageDraw.Draw(self.image_base, ImageConst.DRAW_MODE.value)

            # Draw status shape if provided
            if self.icon_shape is not None:
                draw = ImageFunctions.add_status_icon(draw, self.icon_shape, self.config.icon_padding,
                                                      self.config.icon_size, self.config.icon_width,
                                                      self.config.icon_opacity)

            # Draw text(s) if necessary
            if self.config.add_text:
                self.add_text_to_image(draw, self.config.font_file, self.image_base.height, self.epd.width,
                                       self.title_text, self.artist_text, self.config.title_loc, self.config.artist_loc,
                                       self.config.padding, self.config.opacity, self.config.title_size,
                                       self.config.artist_size, self.config.box_to_floor, self.config.box_to_edge,
                                       crop_left, crop_right)

            self.display_image_on_epd(self.image_base, self.epd)
            logging.shutdown()

        except EPDNotFoundError:
            warnings.warn(f"Couldn't find {self.config.display_type}")
            exit()

        except IOError as e:
            logging.info(e)

        except KeyboardInterrupt:
            logging.info("ctrl + c:")
            self.epd.close()
            exit()
