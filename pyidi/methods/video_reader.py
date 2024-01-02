"""
Module for reading video files from high-speed video recordings. Based on pyMRAW.

@author: Ivan Tomac (itomac@fesb.hr), Klemen Zaletelj (klemen.zaletelj@fs.uni-lj.si), Jaka Javh (jaka.javh@fs.uni-lj.si), Janko Slavič (janko.slavic@fs.uni-lj.si)
"""

import os
import xmltodict
# import warnings 
import pyMRAW
import numpy as np
import imageio.v3 as iio

SUPPORTED_IMAGE_FORMATS = ['png', 'tif', 'tiff', 'bmp', 'jpg', 'jpeg']
PYAV_SUPPORTED_VIDEO_FORMATS = ['avi', 'mkv', 'mp4', 'mov', 'm4v', 'wmv', 'webm', 'flv', 'ogg', 'ogv']
SUPPORTED_EFFECTIVE_BIT_SIDE = ['lower', 'higher']

class VideoReader:
    """
    Manages reading of high-speed video recordings. The video recording can be any
    of the supported file formats which includes image streams, video files or memory 
    map for `mraw` file format.
    """
    def __init__(self, cih_file):
        """
        The video recording is initialized by providing the path to the `cih(x)` file. 
        The `cih` file is a configuration file that contains meta data about the video
        recording. The `cih` file is generated by the camera software (PFV - Photron
        FASTCAM Viewer) and is located in the same folder as the video recording. It is
        assumed that the `cih(x)` file has the same name as the video recording. In the
        case of image stream, file sequence must be named in form:
        `cih-file-name_%d.ext`, where `%d` is the literal for frame number in form 
        `0, 1, ..., 10,... n` and `ext` is the supported file extension.
        The `cih` can be generated manually by the user, but it must contain the
        information provided in the following example:
            ```
            #Camera Information Header
            Date : 2023/07/09
            Camera Type : Blender 3.3.8.
            Record Rate(fps) : 20000
            Shutter Speed(s) : None
            Total Frame : 2500
            Image Width : 1024
            Image Height : 1024
            File Format : PNG
            EffectiveBit Depth : 16
            Color Bit : 16
            Comment Text : Generated sequence. Modify measurement info in created .cih file if necessary.
            ```

        :param cih_file: path to the `cih(x)` file `path/cih-file-name.cih(x)`
        :type cih_file: str
        """

        wanted_info = ['Date',
                    'Camera Type',
                    'Record Rate(fps)',
                    'Shutter Speed(s)',
                    'Total Frame',
                    'Image Width',
                    'Image Height',
                    'File Format',
                    'EffectiveBit Depth',
                    'Comment Text',
                    'Color Bit']
        self.info = self._get_cih(cih_file)
        
        if not all(_ in self.info.keys() for _ in wanted_info):
            raise ValueError('Missing mandatory keys in cih file!')
        
        self.root = os.path.split(cih_file)[0]
        self.filename = os.path.splitext(os.path.split(cih_file)[1])[0]
        self.N = self.info['Total Frame']
        self.image_width = self.info['Image Width']
        self.image_height = self.info['Image Height']

        if self.info['File Format'].lower() == 'mraw':
            # f_name = self.filename + '.' + self.info['File Format'].lower()
            # input_file = os.path.join(self.root, f_name)
            self.mraw, _ = pyMRAW.load_video(cih_file)
        return None
    
    def get_frame(self, frame_number, *args):
        """
        Returns the `frame_number`-th frame from the video.
        """
        if frame_number < 0 or frame_number >= self.info['Total Frame']:
            raise ValueError('Frame number exceeds total frame number!')

        if self.info['File Format'].lower() == 'mraw':
            # return self._get_frame_from_mraw_file(frame_number)
            return self.mraw[frame_number]

        if self.info['File Format'].lower() in SUPPORTED_IMAGE_FORMATS:
            image = self._get_frame_from_image_stream(frame_number)

        elif self.info['File Format'].lower() in PYAV_SUPPORTED_VIDEO_FORMATS:
            image = self._get_frame_from_video_file(frame_number, *args)

        else:
            raise ValueError('Unsupported file format!')

        if self.info['Color Bit'] == '8':
            return np.asarray(image, dtype=np.uint8)
        return np.asarray(image, dtype=np.uint16)

    # def _generate_memmap(self, filename):
    #     """
    #     Generates a memory map for the video file.
    #     """
    #     if self.info['File Format'].lower() != 'mraw':
    #         raise ValueError('Memory map can only be generated for mraw files!')
    #     shape = (self.N, self.image_height, self.image_width)
    #     if self.info['Color Bit'] == '8':
    #         self.mraw = np.memmap(filename, dtype=np.uint8, mode='r', shape=shape)
    #     else:
    #         self.mraw = np.memmap(filename, dtype=np.uint16, mode='r', shape=shape)        
    #     return None
    
    # def close_memmap(self):
    #     """
    #     Closes the memory map.
    #     """
    #     if hasattr(self, 'mraw'):
    #         self.mraw.close()
    #     else:
    #         raise ValueError('No memory map to close!')
    #     return None

    def _get_frame_from_image_stream(self, frame_number):
        """Reads the frame from the image stream.

        :param frame_number: frame number
        :return: image
        """
        f_name = self.filename + f'_{frame_number:d}.' + self.info['File Format'].lower()
        input_file = os.path.join(self.root, f_name)
        return iio.imread(input_file)
    
    def _get_frame_from_video_file(self, frame_number, to_grayscale=True):
        """Reads the frame from the video file which is supported by the
        `imagio.v3` `pyav` plug-in.

        :param frame_number: frame number
        :param to_grayscale: convert to grayscale, defaults to True
        :return: image
        """
        f_name = self.filename + '.' + self.info['File Format'].lower()
        input_file = os.path.join(self.root, f_name)
        image = iio.imread(input_file, index=frame_number, plugin='pyav')

        if to_grayscale and len(image.shape)==3:
            return np.dot(image, [0.2989, 0.5870, 0.1140]) # convert to grayscale
        return image
    
    # def _get_frame_from_mraw_file(self, frame_number):
    #     """Reads the frame from the mraw file. Generates a memory map if it does not
    #     exist.

    #     :param frame_number: frame number
    #     :return: image
    #     """
    #     if not hasattr(self, 'mraw'):
    #         f_name = self.filename + '.' + self.info['File Format'].lower()
    #         input_file = os.path.join(self.root, f_name)
    #         self._generate_memmap(input_file)
    #     return self.mraw[frame_number]

    def _get_cih(self, filename):
        """Function reads the CIH(X) - Camera Information Header file and read data
            into dictionary.
            CIH - metadata in text file format
            CIHX - metadata in xml file format

        The function is copied form pyMRAW and lines that performs checking of file
        format are removed.

        :param filename: path to the CIH(X) file
        :return: dictionary with CIH(X) data
        """
        name, ext = os.path.splitext(filename)
        if ext == '.cih':
            cih = dict()
            # read the cif header
            with open(filename, 'r') as f:
                for line in f:
                    if line == '\n': #end of cif header
                        break
                    line_sp = line.replace('\n', '').split(' : ')
                    if len(line_sp) == 2:
                        key, value = line_sp
                        try:
                            if '.' in value:
                                value = float(value)
                            else:
                                value = int(value)
                            cih[key] = value
                        except:
                            cih[key] = value

        elif ext == '.cihx':
            with open(filename, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                first_last_line = [ i for i in range(len(lines)) if '<cih>' in lines[i] or '</cih>' in lines[i] ]
                xml = ''.join(lines[first_last_line[0]:first_last_line[-1]+1])

            raw_cih_dict = xmltodict.parse(xml)
            cih = {
                'Date': raw_cih_dict['cih']['fileInfo']['date'], 
                'Camera Type': raw_cih_dict['cih']['deviceInfo']['deviceName'],
                'Record Rate(fps)': float(raw_cih_dict['cih']['recordInfo']['recordRate']),
                'Shutter Speed(s)': float(raw_cih_dict['cih']['recordInfo']['shutterSpeed']),
                'Total Frame': int(raw_cih_dict['cih']['frameInfo']['totalFrame']),
                'Original Total Frame': int(raw_cih_dict['cih']['frameInfo']['recordedFrame']),
                'Image Width': int(raw_cih_dict['cih']['imageDataInfo']['resolution']['width']),
                'Image Height': int(raw_cih_dict['cih']['imageDataInfo']['resolution']['height']),
                'File Format': raw_cih_dict['cih']['imageFileInfo']['fileFormat'],
                'EffectiveBit Depth': int(raw_cih_dict['cih']['imageDataInfo']['effectiveBit']['depth']),
                'EffectiveBit Side': raw_cih_dict['cih']['imageDataInfo']['effectiveBit']['side'],
                'Color Bit': int(raw_cih_dict['cih']['imageDataInfo']['colorInfo']['bit']),
                'Comment Text': raw_cih_dict['cih']['basicInfo'].get('comment', ''),
            }

        else:
            raise Exception('Unsupported configuration file ({:s})!'.format(ext))

        # check exceptions
        # ff = cih['File Format']
        # if ff.lower() not in SUPPORTED_FILE_FORMATS:
        #     raise Exception('Unexpected File Format: {:g}.'.format(ff))
        # bits = cih['Color Bit']
        # if bits < 12:
        #     warnings.warn('Not 12bit ({:g} bits)! clipped values?'.format(bits))
        #             # - may cause overflow')
        #             # 12-bit values are spaced over the 16bit resolution - in case of photron filming at 12bit
        #             # this can be meanded by dividing images with //16
        # if cih['EffectiveBit Depth'] != 12:
        #     warnings.warn('Not 12bit image!')
        # ebs = cih['EffectiveBit Side']
        # if ebs.lower() not in SUPPORTED_EFFECTIVE_BIT_SIDE:
        #     raise Exception('Unexpected EffectiveBit Side: {:g}'.format(ebs))
        # if (cih['File Format'].lower() == 'mraw') & (cih['Color Bit'] not in [8, 12, 16]):
        #     raise Exception('pyMRAW only works for 8-bit, 12-bit and 16-bit files!')
        # if cih['Original Total Frame'] > cih['Total Frame']:
        #     warnings.warn('Clipped footage! (Total frame: {}, Original total frame: {})'.format(cih['Total Frame'], cih['Original Total Frame'] ))

        return cih
