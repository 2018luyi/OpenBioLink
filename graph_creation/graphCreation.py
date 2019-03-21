import inspect
import os

from tqdm import tqdm

import graph_creation.graphCreationConfig as glob
import graph_creation.utils as utils
from graph_creation.graphCreator import GraphCreator
from graph_creation.graphWriter import GraphWriter
from graph_creation.metadata_edge.edgeOntoMetadata import EdgeOntoMetadata
from graph_creation.metadata_edge.edgeRegularMetadata import EdgeRegularMetadata
from graph_creation.metadata_edge.tnEdgeRegularMetadata import TnEdgeRegularMetadata
from .file_downloader.fileDownloader import *
from .file_processor.fileProcessor import *
from .file_reader.fileReader import *
from .file_writer.fileWriter import *
from .metadata_db_file import *
from .metadata_infile import *
from .userInteractor import UserInteractor


class Graph_Creation():
    def __init__(self, folder_path, use_db_metadata_classes = None, use_edge_metadata_classes = None):
        #fixme how to decouple directed?
        glob.FILE_PATH = folder_path
        glob.O_FILE_PATH = os.path.join(folder_path, 'o_files')
        glob.IN_FILE_PATH = os.path.join(folder_path, 'in_files')

        if not os.path.exists(glob.FILE_PATH):
            os.makedirs(glob.FILE_PATH)

        self.db_file_metadata = [x() for x in utils.get_leaf_subclasses(DbMetadata)]
        self.file_readers = [x() for x in utils.get_leaf_subclasses(FileReader)]
        self.file_processors = [x() for x in utils.get_leaf_subclasses(FileProcessor)]
        self.infile_metadata = [x(glob.IN_FILE_PATH) for x in utils.get_leaf_subclasses(InfileMetadata)]
        self.edge_metadata = [x(glob.QUALITY) for x in utils.get_leaf_subclasses(EdgeRegularMetadata)] + [x(glob.QUALITY) for x in utils.get_leaf_subclasses(EdgeOntoMetadata)]
        self.tn_edge_metadata = [x(glob.QUALITY) for x in utils.get_leaf_subclasses(TnEdgeRegularMetadata)]

        self.dbType_reader_map = utils.cls_list_to_dic(self.file_readers, 'dbType')
        self.readerType_processor_map = utils.cls_list_to_dic(self.file_processors, 'readerType')
        self.infileType_inMetadata_map = {x.infileType: x for x in self.infile_metadata}


        #if not glob.DIRECTED:
        ## remove onto
        #    if use_edge_metadata_classes is None: #todo test
        #        use_edge_metadata_classes = [x(glob.QUALITY) for x in utils.get_leaf_subclasses(EdgeRegularMetadata)]
        #    else:
        #        temp_use_edge_metadata_classes =[]
        #        for edge_class in use_edge_metadata_classes:
        #            if inspect.isclass(edge_class):
        #                if not issubclass(edge_class, EdgeOntoMetadata):
        #                    temp_use_edge_metadata_classes.append(edge_class())
        #            else:
        #                if not issubclass(type(edge_class), EdgeOntoMetadata):
        #                    temp_use_edge_metadata_classes.append(edge_class)
        #        use_edge_metadata_classes = temp_use_edge_metadata_classes
        #        #use_edge_metadata_classes = [x for x in use_edge_metadata_classes if not issubclass(type(x), EdgeOntoMetadata)] #todo better way to identify onto edges?

        # use only the desired sources
        if use_db_metadata_classes is not None:
            self.init_custom_sources_bottom_up(use_db_metadata_classes)
        if use_edge_metadata_classes is not None:
            self.init_custom_sources_top_down(use_edge_metadata_classes)


# ----------- download ----------

    def download_db_files(self):
        skip = None
        for_all = False
        if not glob.INTERACTIVE_MODE:
            skip =glob.SKIP_EXISTING_FILES
            for_all = True
        if not os.path.exists(glob.O_FILE_PATH):
            os.makedirs(glob.O_FILE_PATH)
        for db_file in tqdm(self.db_file_metadata):
            o_file_path = os.path.join(glob.O_FILE_PATH, db_file.ofile_name)
            if not for_all:
                skip, for_all = UserInteractor.skip_existing_files(o_file_path)
            if not (skip and os.path.isfile(o_file_path)):
                FileDownloader.download(db_file.url, o_file_path)


# ----------- create input files ----------

    def create_input_files(self):
        skip = None
        for_all = False
        if not glob.INTERACTIVE_MODE:
            skip =glob.SKIP_EXISTING_FILES
            for_all = True
        if not os.path.exists(glob.IN_FILE_PATH):
            os.makedirs(glob.IN_FILE_PATH)
        for reader in tqdm(self.file_readers):
            if reader.readerType in self.readerType_processor_map:

                #check beforehand if read in content is processed as parsing can be time consuming
                all_files_exist = True
                for processor in self.readerType_processor_map[reader.readerType]:
                    if not os.path.isfile(os.path.join(glob.IN_FILE_PATH, (self.infileType_inMetadata_map[processor.infileType]).csv_name)):
                        all_files_exist = False
                if all_files_exist and not for_all and self.readerType_processor_map[reader.readerType]:
                    first_processor = self.readerType_processor_map[reader.readerType][0]
                    first_processor_out_path = os.path.join(glob.IN_FILE_PATH, (self.infileType_inMetadata_map[first_processor.infileType]).csv_name)
                    skip, for_all = UserInteractor.skip_existing_files(first_processor_out_path)
                if not (skip and all_files_exist): #fixme test skip

                    #execute processors
                    in_data = reader.read_file()
                    #fixme  ResourceWarning: Enable tracemalloc to get the object allocation traceback
                    for processor in self.readerType_processor_map[reader.readerType]:
                        out_file_path = os.path.join(glob.IN_FILE_PATH, (self.infileType_inMetadata_map[processor.infileType]).csv_name)
                        if not for_all:
                            skip, for_all = UserInteractor.skip_existing_files(out_file_path)
                        if not (skip and os.path.isfile(out_file_path)):
                            out_data = processor.process(in_data)
                            FileWriter.wirte_to_file(out_data, out_file_path)
            else:
                print ('\nWARNING: There is no processor for the Reader '+ str(reader.readerType))


# ----------- create graph ----------

    def create_graph(self):
        #create and empty stat files
        #todo check for existing files, ask for exit
        gc = GraphCreator()
        tn_path_no_mappings = os.path.join(glob.FILE_PATH, glob.TN_ID_NO_MAPPING_FILE_NAME)
        tn_path_stats = os.path.join(glob.FILE_PATH, glob.TN_STATS_FILE_NAME)
        path_no_mappings = os.path.join(glob.FILE_PATH, glob.ID_NO_MAPPING_FILE_NAME)
        path_stats = os.path.join(glob.FILE_PATH, glob.STATS_FILE_NAME)
        open(tn_path_no_mappings, 'w').close()
        open(tn_path_stats, 'w').close()
        open(path_no_mappings, 'w').close()
        open(path_stats, 'w').close()
        #create graph
        nodes_dic, edges_dic = gc.meta_edges_to_graph(self.edge_metadata)
        GraphWriter.output_graph(nodes_dic, edges_dic, one_file_sep='\t')
        #create TN edges
        tn_nodes_dic, tn_edges_dic = gc.meta_edges_to_graph(self.tn_edge_metadata, tn = True)
        GraphWriter.output_graph(tn_nodes_dic, tn_edges_dic, one_file_sep='\t', prefix='TN_') #todo btter one?






# ----------- helper init functions ----------

    def init_custom_sources_bottom_up(self, use_db_metdata_classes):
        """hepler __init__ function for costum db_metadata_classes"""

        self.db_file_metadata = []

        # remove dbMetadata from list
        # make sure to use instances of classes
        for x in use_db_metdata_classes:
            if inspect.isclass(x):
                self.db_file_metadata.append(x())
            else:
                self.db_file_metadata.append(x)

        # remove readers
        keep_dbType = [x.dbType for x in self.db_file_metadata]
        print('readers removed: ' + str( [x.__class__.__name__ for x in self.file_readers if x.dbType not in keep_dbType]))
        self.file_readers = [x for x in self.file_readers if x.dbType in keep_dbType]
        self.dbType_reader_map = utils.cls_list_to_dic(self.file_readers, 'dbType')

        #remove processors
        keep_readerType = [x.readerType for x in self.file_readers]
        print('processors removed: %s' %(str( [x.__class__.__name__ for x in self.file_processors if x.readerType not in keep_readerType])))
        self.file_processors = [x for x in self.file_processors if x.readerType in keep_readerType]
        self.readerType_processor_map = utils.cls_list_to_dic(self.file_processors, 'readerType')

        #remove infile metadata
        keep_infileType = [x.infileType for x in self.file_processors]
        print('processors removed: ' + str( [x.__class__.__name__ for x in self.infile_metadata if x.infileType not in keep_infileType]))
        self.infile_metadata = [x for x in self.infile_metadata if x.infileType in keep_infileType]
        self.infileType_inMetadata_map = {x.infileType: x for x in self.infile_metadata}

        # remove edge metadata
        print('edges removed: ' + str( [x.__class__.__name__ for x in self.edge_metadata + self.tn_edge_metadata if x.EDGE_INMETA_CLASS.INFILE_TYPE not in keep_infileType]))
        self.edge_metadata = [x for x in self.edge_metadata if x.EDGE_INMETA_CLASS.INFILE_TYPE in keep_infileType]
        self.tn_edge_metadata = [x for x in self.tn_edge_metadata if x.EDGE_INMETA_CLASS.INFILE_TYPE in keep_infileType]

        # check for deleted dependencies of mappings
        additional_remove_metaEdges = []
        additional_remove_mapping_infileType = []
        for metaEdge in self.edge_metadata + self.tn_edge_metadata:
            mappings = [metaEdge.MAP1_META_CLASS, metaEdge.MAP2_META_CLASS, metaEdge.MAP1_ALT_ID_META_CLASS,
                        metaEdge.MAP2_ALT_ID_META_CLASS]
            for mapping in mappings:

                if mapping is not None and mapping.INFILE_TYPE not in keep_infileType:
                    additional_remove_metaEdges.append(metaEdge)
                    additional_remove_mapping_infileType.append(mapping.INFILE_TYPE)
        if len(additional_remove_metaEdges)>0:
            UserInteractor.ask_for_exit('\nWARNING: Due to manual exclusion of DB resources, also the edges: ' +
                                        str([x.__class__.__name__ for x in additional_remove_metaEdges]) +
                                        '\n will be removed due to deleted dependencies of used mappings (i.e. ' +
                                        str([str(x) for x in additional_remove_mapping_infileType])+
                                        '\n Consider manually exclude edges instead of DB resources.')

            self.edge_metadata = [x for x in self.edge_metadata if x not in additional_remove_metaEdges]
            self.tn_edge_metadata = [x for x in self.tn_edge_metadata if x not in additional_remove_metaEdges]


    def init_custom_sources_top_down(self, use_edge_metdata_classes):
        """hepler __init__ function for custom edge_metadata_classes"""

        #remove edge_metadata
        print ('Edge Metadata removed: ' + str([x.__class__.__name__ for x in self.edge_metadata if x.EDGE_INMETA_CLASS not in [y.EDGE_INMETA_CLASS for y in use_edge_metdata_classes]]))
        self.edge_metadata = []

        for x in use_edge_metdata_classes:
            if inspect.isclass(x):
                self.edge_metadata.append(x())
            else:
                self.edge_metadata.append(x)

        # remove inMetadata
        infileType_edgeMetadata_map = utils.cls_list_to_dic(self.edge_metadata, 'EDGE_INMETA_CLASS.INFILE_TYPE')
        infileType_edgeMetadata_map.update(utils.cls_list_to_dic(self.edge_metadata,'MAP1_META_CLASS.INFILE_TYPE', lambda a: a.MAP1_META_CLASS is not None ))
        infileType_edgeMetadata_map.update(utils.cls_list_to_dic(self.edge_metadata,'MAP2_META_CLASS.INFILE_TYPE', lambda a: a.MAP2_META_CLASS is not None ))
        infileType_edgeMetadata_map.update(utils.cls_list_to_dic(self.edge_metadata,'MAP1_ALT_ID_META_CLASS.INFILE_TYPE', lambda a: a.MAP1_ALT_ID_META_CLASS is not None ))
        infileType_edgeMetadata_map.update(utils.cls_list_to_dic(self.edge_metadata,'MAP2_ALT_ID_META_CLASS.INFILE_TYPE', lambda a: a.MAP2_ALT_ID_META_CLASS is not None ))

        infileType_edgeMetadata_map.update(utils.cls_list_to_dic(self.tn_edge_metadata, 'EDGE_INMETA_CLASS.INFILE_TYPE'))
        infileType_edgeMetadata_map.update(utils.cls_list_to_dic(self.tn_edge_metadata,'MAP1_META_CLASS.INFILE_TYPE', lambda a: a.MAP1_META_CLASS is not None ))
        infileType_edgeMetadata_map.update(utils.cls_list_to_dic(self.tn_edge_metadata,'MAP2_META_CLASS.INFILE_TYPE', lambda a: a.MAP2_META_CLASS is not None ))
        infileType_edgeMetadata_map.update(utils.cls_list_to_dic(self.tn_edge_metadata,'MAP1_ALT_ID_META_CLASS.INFILE_TYPE', lambda a: a.MAP1_ALT_ID_META_CLASS is not None ))
        infileType_edgeMetadata_map.update(utils.cls_list_to_dic(self.tn_edge_metadata,'MAP2_ALT_ID_META_CLASS.INFILE_TYPE', lambda a: a.MAP2_ALT_ID_META_CLASS is not None ))

        keep_infileTypes = list(infileType_edgeMetadata_map.keys())
        print('Infile Metadata removed: ' + str([x.__class__.__name__ for x in self.infile_metadata if x.infileType not in keep_infileTypes]))
        self.infile_metadata = [x for x in self.infile_metadata if x.infileType in keep_infileTypes]
        self.infileType_inMetadata_map = {x.infileType: x for x in self.infile_metadata}

        # remove processors
        print('Processors removed: ' + str([x.__class__.__name__ for x in self.file_processors if x.infileType not in keep_infileTypes]))
        self.file_processors = [x for x in self.file_processors if x.infileType in keep_infileTypes]
        self.readerType_processor_map = utils.cls_list_to_dic(self.file_processors, 'readerType')

        #remove readers
        keep_readerType = list(self.readerType_processor_map.keys())
        print('Readers removed: ' + str([x.__class__.__name__ for x in self.file_readers if x.readerType not in keep_readerType]))
        self.file_readers = [x for x in self.file_readers if x.readerType in keep_readerType]
        self.dbType_reader_map = utils.cls_list_to_dic(self.file_readers, 'dbType')

        #remove db_metadata
        keep_dbType = list(self.dbType_reader_map.keys())
        print('DB_source removed: ' + str([x.__class__.__name__ for x in self.db_file_metadata if x.dbType not in keep_dbType]))

        self.db_file_metadata = [x for x in self.db_file_metadata if x.dbType in keep_dbType]
