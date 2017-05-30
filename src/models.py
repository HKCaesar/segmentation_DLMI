from keras.layers import  Lambda, AveragePooling3D, MaxPooling3D, PReLU, Input, merge, \
    Merge, BatchNormalization, Conv3D, Concatenate, Add#, concatenate ,Convolution3D
from keras.models import Sequential, Model
from keras.optimizers import RMSprop, Adam
from keras.regularizers import L1L2

from src.activations import elementwise_softmax_3d
from src.losses import categorical_crossentropy_3d
from src.layers import Upsampling3D_mod
from src.metrics import accuracy, dice_whole, dice_enhance, dice_core, recall_0,recall_1,recall_2,recall_3,\
    recall_4, precision_0,precision_1,precision_2,precision_3,precision_4



class BratsModels(object):
    """ Interface that allows you to save and load models and their weights """

    # ------------------------------------------------ CONSTANTS ------------------------------------------------ #

    DEFAULT_MODEL = 'u_net'

    # ------------------------------------------------- METHODS ------------------------------------------------- #

    @classmethod
    def get_model(cls, num_modalities, segment_dimensions, num_classes, model_name=None, weights_filename=None,
                  **kwargs):
        """
        Returns the compiled model specified by its name.
        If no name is given, the default model is returned, which corresponds to the
        hand-picked model that performs the best.

        Parameters
        ----------
        num_modalities : int
            Number of modalities used as input channels
        segment_dimensions : tuple
            Tuple with 3 elements that specify the shape of the input segments
        num_classes : int
            Number of output classes to be predicted in the segmentation
        model_name : [Optional] String
            Name of the model to be returned
        weights_filename: [Optional] String
            Path to the H5 file containing the weights of the trained model. The user must ensure the
            weights correspond to the model to be loaded.

        Returns
        -------
        keras.Model
            Compiled keras model
        tuple
            Tuple with output size (necessary to adjust the ground truth matrix's size),
            or None if output size is the sames as segment_dimensions.

        Raises
        ------
        TypeError
            If model_name is not a String or None
        ValueError
            If the model specified by model_name does not exist
        """
        if model_name is None:
            return cls.get_model(num_modalities, segment_dimensions, num_classes, model_name=cls.DEFAULT_MODEL,
                                 weights_filename=weights_filename, **kwargs)
        if isinstance(model_name, basestring):
            try:

                model_getter = cls.__dict__[model_name]
                return model_getter.__func__(num_modalities, segment_dimensions, num_classes,
                                             weights_filename=weights_filename, **kwargs)
            except KeyError:
                raise ValueError('Model {} does not exist. Use the class method {} to know the available model names'
                                 .format(model_name, 'get_model_names'))
        else:
            raise TypeError('model_name must be a String/Unicode sequence or None')

    @classmethod
    def get_model_names(cls):
        """
        List of available models' names

        Returns
        -------
        List
            Names of the available model names to be used in get_model(model_name) method
        """

        def filter_functions(attr_name):
            tmp = ('model' not in attr_name) and ('MODEL' not in attr_name)
            return tmp and ('__' not in attr_name) and ('BASE' not in attr_name)

        return filter(filter_functions, cls.__dict__.keys())

    @staticmethod
    def u_net(num_modalities, segment_dimensions, num_classes, weights_filename=None, pre_train = False):
        """
        U-Net based architecture for segmentation (http://lmb.informatik.uni-freiburg.de/people/ronneber/u-net/)
            - Convolutional layers: 3x3x3 filters, stride 1, same border
            - Max pooling: 2x2x2
            - Upsampling layers: 2x2x2
            - Activations: ReLU
            - Classification layer: 1x1x1 kernel, and there are as many kernels as classes to be predicted. Element-wise
              softmax as activation.
            - Loss: 3D categorical cross-entropy
            - Optimizer: Adam with lr=0.001, beta_1=0.9, beta_2=0.999 and epsilon=10 ** (-4)
            - Regularization: L1=0.000001, L2=0.0001
            - Weights initialization: He et al normal initialization (https://arxiv.org/abs/1502.01852)

        Returns
        -------
        keras.model
            Compiled Sequential model
        tuple (dim1, dim2, dim3)
            Output shape computed from segment_dimensions and the convolutional architecture
        """
        if not isinstance(segment_dimensions, tuple) or len(segment_dimensions) != 3:
            raise ValueError('segment_dimensions must be a tuple with length 3, specifying the shape of the '
                             'input segment')

        # for dim in segment_dimensions:
        #     assert dim % 32 == 0  # As there are 5 (2, 2, 2) max-poolings, 2 ** 5 is the minimum input size

        # Hyperaparametre values
        lr = 0.0005
        beta_1 = 0.9
        beta_2 = 0.999
        epsilon = 10 ** (-8 )
        L1_reg = 0.000001
        L2_reg = 0.0001
        initializer = 'he_normal'
        pool_size = (2, 2, 2)

        # Compute input shape, receptive field and output shape after softmax activation
        input_shape = (num_modalities,) + segment_dimensions
        output_shape = segment_dimensions
        print 'shapes (in and out)'
        print str(input_shape)
        print str(output_shape)
        # Activations, regularizers and optimizers
        softmax_activation = Lambda(elementwise_softmax_3d, name='Softmax')
        regularizer = L1L2(l1=L1_reg, l2=L2_reg)
        optimizer = Adam(lr=lr, beta_1=beta_1, beta_2=beta_2, epsilon=epsilon, clipnorm = 1.)

        # Architecture definition

        # First level
        x = Input(shape=input_shape, name='U-net_input')
        tmp = Conv3D(8, (3, 3, 3), kernel_initializer=initializer, name='conv_1.1',
                     activation='relu', padding='same')(x)

        tmp = BatchNormalization(axis=1, name='batch_norm_1.1')(tmp)
        tmp = Conv3D(8, (3, 3, 3), kernel_initializer=initializer, name='conv_1.2',  activation='relu',
                     padding='same')(tmp)
        tmp = BatchNormalization(axis=1, name='batch_norm_1.2')(tmp)
        z1 = Concatenate(axis=1)([tmp, x])
        end_1 = MaxPooling3D(pool_size=pool_size, name='pool_1')(z1)

        # Second level
        tmp = Conv3D(16, (3, 3, 3), kernel_initializer=initializer, name='conv_2.1',  activation='relu',
                     padding='same')(end_1)
        tmp = BatchNormalization(axis=1, name='batch_norm_2.1')(tmp)
        tmp = Conv3D(16, (3, 3, 3), kernel_initializer=initializer, name='conv_2.2',  activation='relu',
                     padding='same')(tmp)
        tmp = BatchNormalization(axis=1, name='batch_norm_2.2')(tmp)
        z2 = Concatenate(axis=1)([tmp, end_1])
        end_2 = MaxPooling3D(pool_size=pool_size, name='pool_2')(z2)

        # Third level
        tmp = Conv3D(32, (3, 3, 3), kernel_initializer=initializer, name='conv_3.1',  activation='relu',
                     padding='same')(end_2)
        tmp = BatchNormalization(axis=1, name='batch_norm_3.1')(tmp)
        tmp = Conv3D(32, (3, 3, 3), kernel_initializer=initializer, name='conv_3.2',  activation='relu',
                     padding='same')(tmp)
        tmp = BatchNormalization(axis=1, name='batch_norm_3.2')(tmp)
        z3 = Concatenate(axis=1)([tmp, end_2])
        end_3 = MaxPooling3D(pool_size=pool_size, name='pool_3')(z3)

        # Fourth level
        tmp = Conv3D(64, (3, 3, 3), kernel_initializer=initializer, name='conv_4.1',  activation='relu',
                     padding='same')(end_3)
        tmp = BatchNormalization(axis=1, name='batch_norm_4.1')(tmp)
        tmp = Conv3D(64, (3, 3, 3), kernel_initializer=initializer, name='conv_4.2',  activation='relu',
                     padding='same')(tmp)
        tmp = BatchNormalization(axis=1, name='batch_norm_4.2')(tmp)
        z4 = Concatenate(axis=1)([tmp, end_3])
        end_4 = MaxPooling3D(pool_size=pool_size, name='pool_4')(z4)

        # Fifth level
        tmp = Conv3D(128, (3, 3, 3), kernel_initializer=initializer, name='conv_5.1',  activation='relu',
                     padding='same')(end_4)
        tmp = BatchNormalization(axis=1, name='batch_norm_5.1')(tmp)
        tmp = Conv3D(128, (3, 3, 3), kernel_initializer=initializer, name='conv_5.2',  activation='relu',
                     padding='same')(tmp)          #inflection point
        tmp = BatchNormalization(axis=1, name='batch_norm_5.2')(tmp)
        z5 = Concatenate(axis=1)([tmp, end_4])
        end_5 = Upsampling3D_mod(size=pool_size, name='up_5')(z5)

        # Fourth level
        tmp = Concatenate(axis=1)([end_5, z4])#, axis=1)#, name='merge 4')
        tmp = Conv3D(64, (3, 3, 3), kernel_initializer=initializer, name='conv_4.3', activation='relu',
                     padding='same')(tmp)
        tmp = BatchNormalization(axis=1, name='batch_norm_4.3')(tmp)
        tmp = Conv3D(64, (3, 3, 3), kernel_initializer=initializer, name='conv_4.4',  activation='relu',
                     padding='same')(tmp)
        tmp = BatchNormalization(axis=1, name='batch_norm_4.4')(tmp)
        tmp = Concatenate(axis=1)([tmp, end_5])
        end_42 = Upsampling3D_mod(size=pool_size, name='up_4')(tmp)

        # Third level
        tmp = Concatenate(axis=1)([end_42, z3])#, axis=1, name='merge 3')
        tmp = Conv3D(32, (3, 3, 3), kernel_initializer=initializer, name='conv_3.3',  activation='relu',
                     padding='same')(tmp)
        tmp = BatchNormalization(axis=1, name='batch_norm_3.3')(tmp)
        tmp = Conv3D(32, (3, 3, 3), kernel_initializer=initializer, name='conv_3.4',  activation='relu',
                     padding='same')(tmp)
        tmp = BatchNormalization(axis=1, name='batch_norm_3.4')(tmp)
        tmp = Concatenate(axis=1)([tmp, end_42])

        end_32 = Upsampling3D_mod(size=pool_size, name='up_3')(tmp)


        # Second level
        tmp = Concatenate(axis=1)([end_32, z2])
        tmp = Conv3D(16, (3, 3, 3), kernel_initializer=initializer, name='conv_2.3',  activation='relu',
                     padding='same')(tmp)
        tmp = BatchNormalization(axis=1, name='batch_norm_2.3')(tmp)
        tmp = Conv3D(16, (3, 3, 3), kernel_initializer=initializer, name='conv_2.4',  activation='relu',
                     padding='same')(tmp)
        tmp = BatchNormalization(axis=1, name='batch_norm_2.4')(tmp)
        tmp = Concatenate(axis=1)([tmp, end_32])
        end_22 = Upsampling3D_mod(size=pool_size, name='up_2')(tmp)

        # First level
        tmp = Concatenate(axis=1)([end_22, z1])
        tmp = Conv3D(8, (3, 3, 3), kernel_initializer=initializer, name='conv_1.3',  activation='relu',
                     padding='same')(tmp)
        tmp = BatchNormalization(axis=1, name='batch_norm_1.3')(tmp)
        tmp = Conv3D(8, (3, 3, 3), kernel_initializer=initializer, name='conv_1.4',  activation='relu',
                     padding='same')(tmp)
        tmp = BatchNormalization(axis=1, name='batch_norm_1.4')(tmp)
        end_12 = Concatenate(axis=1)([tmp,end_22])
        # Classification layer

        classification = Conv3D(num_classes, (1, 1, 1) , kernel_initializer=initializer, kernel_regularizer=regularizer,
                                activation='relu', name='final_convolution')(end_12)
        classification_norm = BatchNormalization(axis=1, name='final_batch_norm')(classification)
        y = softmax_activation(classification_norm)#, output_shape=output_shape)

        print str(y)

        model = Model(inputs=x, outputs=y)
        # if pre_train:
        #     for layer in model.layers[:33]:
        #         layer.trainable = False

        # Create and compile model

        model.compile(
            optimizer=optimizer,
            loss=categorical_crossentropy_3d,
            metrics=[accuracy, dice_whole, dice_core, dice_enhance, recall_0, recall_1, recall_2, recall_3, recall_4,
                     precision_0, precision_1, precision_2, precision_3, precision_4]

        )

        # Load weights if available
        if weights_filename is not None:
            model.load_weights(weights_filename)

        return model, output_shape

