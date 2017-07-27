import nibabel as nib
import numpy as np
import os
from os.path import join
from src.utils.preprocessing import flip_plane, normalize_image

to_int = lambda b: 1 if b else 0

class Subject:
    def __init__(self,
                 data_path,
                 id):

        self.data_path = data_path
        self._id = id

        self.FLAIR_FILE = join(self.data_path,'pre','FLAIR.nii.gz')
        self.T1_FILE = join(self.data_path,'pre','T1.nii.gz')
        self.ROIMASK_FILE = join(self.data_path,'pre','mask_closing.nii.gz')

        self.data_augmentation = False

    @property
    def id(self):
        return self._id

    def get_affine(self):
        return nib.load(self.T1_FILE).affine

    def load_channels(self,normalize = False):
        modalities = []
        modalities.append(nib.load(self.FLAIR_FILE))
        modalities.append(nib.load(self.T1_FILE))

        channels = np.zeros( modalities[0].shape + (2,), dtype=np.float32)

        for index_mod, mod in enumerate(modalities):
            if self.data_augmentation:
                channels[:, :, :, index_mod] = flip_plane(np.asarray(mod.dataobj))
            else:
                channels[:,:,:,index_mod] = np.asarray(mod.dataobj)

            if normalize:
                channels[:, :, :, index_mod] = normalize_image(channels[:,:,:,index_mod], mask = self.load_ROI_mask() )


        return channels

    def load_ROI_mask(self):

        roimask_proxy = nib.load(self.ROIMASK_FILE)
        if self.data_augmentation:
            mask = flip_plane(np.asarray(roimask_proxy.dataobj))
        else:
            mask = np.asarray(roimask_proxy.dataobj)
        return mask.astype('bool')


    def get_subject_shape(self):

        proxy = nib.load(self.T1_FILE)
        return proxy.shape



class Loader():

    def __init__(self, data_path):
        self.data_path = data_path

    @staticmethod
    def create(config_dict):
        return Loader(config_dict['data_dir'])


    def load_subject(self):
        subject = Subject(self.data_path)

        return subject
