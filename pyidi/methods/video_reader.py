"""
Module for reading video files from high-speed video recordings.

@author: Ivan Tomac (itomac@fesb.hr), Klemen Zaletelj (klemen.zaletelj@fs.uni-lj.si), Jaka Javh (jaka.javh@fs.uni-lj.si), Janko Slavič (janko.slavic@fs.uni-lj.si)
"""

import os
import pyMRAW
import numpy as np
import imageio.v3 as iio

PHORTRON_HEADER_FILE = ['cih', 'cihx']
SUPPORTED_IMAGE_FORMATS = ['png', 'tif', 'tiff', 'bmp', 'jpg', 'jpeg', 'gif']
PYAV_SUPPORTED_VIDEO_FORMATS = ['avi', 'mkv', 'mp4', 'mov', 'm4v', 'wmv', 'webm', 'flv', 'ogg', 'ogv']
CHANNELS = {'R': 0, 'G': 1, 'B': 2}
class VideoReader:
    """
    Manages reading of high-speed video recordings. The video recording can be any
    of the supported file formats which includes image streams, video files or memory 
    map for `mraw` file format.
    """
    def __init__(self, input_file):
        """
        The video recording is initialized by providing the path to the image/video file or 
        `cih(x)` file from Photron. For image stream it is enough to provide the path to the
        any image file in the sequence. Image formats that support multiple images, such as 
        `gif`, `tif` are supported too. 
        Video files are supported by the `pyav` plug-in and to allow support of higher bit depth
        then 8 bit upgrade is needed.

        :param input_file: path to the image/video or `cih(x)` file
        :type input_file: str
        """

        self.root, self.file = os.path.split(input_file)
        self.file_format = self.file.split('.')[-1].lower()

        if self.file_format in PHORTRON_HEADER_FILE:
            self.mraw, info = pyMRAW.load_video(input_file)
            self.N = info['Total Frame']
            self.image_width = info['Image Width']
            self.image_height = info['Image Height']
        
        elif self.file_format in SUPPORTED_IMAGE_FORMATS:
            image_prop = iio.improps(input_file)
            if image_prop.n_images is None:
                self.is_n_images = False
                sc_dir = os.scandir(self.root)
                self.frame_files = [f.name for f in sc_dir \
                                    if f.name.endswith(self.file_format) \
                                        or f.name.endswith(self.file_format.upper())]
                self.N = len(self.frame_files)
                self.image_width = image_prop.shape[1]
                self.image_height = image_prop.shape[0]
            else:
                self.is_n_images = True
                self.N = image_prop.n_images
                self.image_width = image_prop.shape[2]
                self.image_height = image_prop.shape[1]
        
        elif self.file_format in PYAV_SUPPORTED_VIDEO_FORMATS:
            video_prop = iio.improps(input_file, plugin='pyav')
            self.N = video_prop.n_images
            self.image_width = video_prop.shape[2]
            self.image_height = video_prop.shape[1]

        else:
            raise ValueError('Unsupported file format!')

        return None
    
    def get_frame(self, frame_number, *args):
        """
        Returns the `frame_number`-th frame from the video.

        :param frame_number: frame number (int)
        :param *args: additional arguments to be passed to the image readers to handle multiple channels in image
        :return: image (monochrome)
        """
        if not 0 <= frame_number < self.N:
            raise ValueError('Frame number exceeds total frame number!')

        if self.file_format in PHORTRON_HEADER_FILE:
            image = self.mraw[frame_number]

        elif self.file_format in SUPPORTED_IMAGE_FORMATS:
            image = self._get_frame_from_image(frame_number, *args)

        elif self.file_format in PYAV_SUPPORTED_VIDEO_FORMATS:
            image = self._get_frame_from_video_file(frame_number, *args)

        return image

    def _get_frame_from_image(self, frame_number, use_channel='Y'):
        """Reads the frame from the image stream. If the image is in RGB format,
        the `use_channel` parameter can be used to select the channel. The supported
        channels are R, G, B and Y (luma).

        :param frame_number: frame number
        :param use_channel: 'R', 'G', 'B' 'Y', None defaults to 'Y'
        :return: image (monochrome)
        """
        if self.is_n_images:
            input_file = os.path.join(self.root, self.file)
            image = iio.imread(input_file, index=frame_number)
        else:
            input_file = os.path.join(self.root, self.frame_files[frame_number])
            image = iio.imread(input_file)

        
        if use_channel is None or len(image.shape) == 2:
            pass
        
        elif use_channel.upper() == 'Y':
            image = _rgb2luma(image[:, :, :3])
        
        elif use_channel.upper() in CHANNELS.keys():
            image = image[:, :, CHANNELS.get(use_channel.upper())]
        
        else:
            raise ValueError('Unsupported channel! Only R, G, B and Y are supported.')
        
        return image
    
    def _get_frame_from_video_file(self, frame_number, use_channel='Y'):
        """Reads the frame from the video file which is supported by the
        `imagio.v3` `pyav` plug-in.

        :param frame_number: frame number
        :param use_channel: convert to grayscale, defaults to True
        :return: image in 8 bit depth (note: needs upgrade to support higher bit depth)
        """
        input_file = os.path.join(self.root, self.file)
        if use_channel == 'Y':
            image = iio.imread(input_file, index=frame_number, plugin='pyav', format='yuv444p')
            image = image.transpose(1, 2, 0)
            image = image[:, :, 0]

        elif use_channel.upper() in CHANNELS.keys():
            image = iio.imread(input_file, index=frame_number, plugin='pyav')
            image = image[:, :, CHANNELS.get(use_channel.upper())]
        
        elif use_channel is None:
            image = iio.imread(input_file, index=frame_number, plugin='pyav')
        
        return image

def _rgb2luma(rgb_image):
    """Converts RGB image to YUV and returns only y Y (luma) component.

    :param rgb_image: RGB image (w, h, channels)
    :return: luma image
    """
    T = np.array([[ 0.29900, -0.16874,  0.50000],
                 [0.58700, -0.33126, -0.41869],
                 [ 0.11400, 0.50000, -0.08131]])
    yuv_image = rgb_image @ T
    return np.asarray(np.around(yuv_image[:, :, 0]), dtype=rgb_image.dtype)