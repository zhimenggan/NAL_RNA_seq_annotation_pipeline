from os import path

def get_lib_path():
    return path.join(path.abspath(path.dirname(__file__)), 'lib')


def get_trimmomatic_jar_path():
    return path.join(get_lib_path(), 'Trimmomatic-0.38', 'trimmomatic-0.38.jar')


def get_fastqc_path():
    return path.join(get_lib_path(), 'FastQC', 'fastqc')


def get_trimmomatic_adapter_path(file_name):
    return path.join(get_lib_path(), 'Trimmomatic-0.38', 'adapters', file_name)


def get_bbmap_adapter_path():
    return path.join(get_lib_path(), 'bbmap', 'resources', 'adapters.fa')


def get_hisat2_command_path(cmd):
    return path.join(get_lib_path(), 'hisat2-2.1.0', cmd)


def get_bbmap_command_path(cmd):
    return path.join(get_lib_path(), 'bbmap', cmd)


def get_gatk_jar_path():
    return path.join(get_lib_path(), 'GenomeAnalysisTK.jar')


def get_picard_jar_path():
    return path.join(get_lib_path(), 'picard.jar')
