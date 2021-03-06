#!/usr/bin/env python3
import os
from os import path
from rnannot.parser import parse_args
from sys import argv, exit
from rnannot.utils import get_trimmomatic_jar_path, get_fastqc_path, get_trimmomatic_adapter_path, get_hisat2_command_path, get_bbmap_command_path, get_bbmap_adapter_path, get_gatk_jar_path, get_picard_jar_path
import subprocess
from zipfile import ZipFile
import gzip
import shutil
from itertools import islice
from six.moves import urllib


def run_pipeline(file, genome, outdir, name, layout, platform, model, download_link):
    # create the output folder
    output_prefix = path.join(outdir, name)
    os.mkdir(output_prefix)

    if platform == 'ABI_SOLID':
        return (
            False,
            'Currently, the colorspace data from ABI_SOLID is not supported')

    # decompress the gz file, becasue some of tools don't accept .gz compressed files
    if genome.endswith('.gz'):
        new_genome_file_name = path.join(output_prefix,
                                         path.basename(genome).rstrip('.gz'))
        with gzip.open(genome, 'rb') as f_in:
            with open(new_genome_file_name, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        genome = new_genome_file_name
    sra_file_name = path.basename(file)
    genome_file_name = path.basename(genome)

    # check if SRA file exist or download it first
    if not path.exists(file):
        urllib.request.urlretrieve(download_link, file)

    # convert SRA file to fastq file(s)
    print('Unpacking the SRA file: {} ...'.format(file))
    f_stdout = open(
        path.join(output_prefix, sra_file_name + '.fastq-dump.log'), 'w')
    f_stderr = open(
        path.join(output_prefix, sra_file_name + '.fastq-dump.errlog'), 'w')
    subprocess.run(
        [
            'fastq-dump', '--dumpbase', '--split-files', '-O', output_prefix,
            file
        ],
        stdout=f_stdout,
        stderr=f_stderr)
    f_stdout.close()
    f_stderr.close()
    # Check if the SRA file is correct or not first
    if layout == 'PAIRED' and (not path.exists(
            path.join(
                output_prefix, sra_file_name + '_1.fastq')) or not path.exists(
                    path.join(output_prefix, sra_file_name + '_1.fastq'))):
        return (
            False,
            "run {} doesn't have paired data. It's not processed.".format(run))

    # Run FastQC first
    # Then, use Trimmomatic to do trimming
    # In the last step, perfom the alignment using HISAT2
    fastqc_path = get_fastqc_path()
    trimmomatic_jar_path = get_trimmomatic_jar_path()
    if layout == 'SINGLE':
        print('QC ...')
        f_stdout = open(
            path.join(output_prefix, sra_file_name + '_1.fastqc.log'), 'w')
        f_stderr = open(
            path.join(output_prefix, sra_file_name + '_1.fastqc.errlog'), 'w')
        subprocess.run(
            [
                fastqc_path, '--outdir', output_prefix,
                path.join(output_prefix, sra_file_name + '_1.fastq')
            ],
            stdout=f_stdout,
            stderr=f_stderr)
        with ZipFile(
                path.join(output_prefix, sra_file_name + '_1_fastqc.zip'),
                'r') as zip_ref:
            zip_ref.extractall(output_prefix)
        f_stdout.close()
        f_stderr.close()
        print('Trimming ...')
        f_stdout = open(
            path.join(output_prefix, sra_file_name + '.trimmomatic.log'), 'w')
        f_stderr = open(
            path.join(output_prefix, sra_file_name + '.trimmomatic.errlog'),
            'w')
        if platform == 'ILLUMINA' and (model.startswith('Illumina HiSeq')
                                       or model.startswith('Illumina MiSeq')):
            subprocess.run(
                [
                    'java', '-jar', trimmomatic_jar_path, 'SE',
                    path.join(output_prefix, sra_file_name + '_1.fastq'),
                    path.join(output_prefix, 'output.fastq'), 'ILLUMINACLIP:' +
                    get_trimmomatic_adapter_path('TruSeq3-SE.fa') + ':2:30:10',
                    'LEADING:3', 'TRAILING:3', 'SLIDINGWINDOW:4:15',
                    'MINLEN:36', 'TOPHRED33'
                ],
                stdout=f_stdout,
                stderr=f_stderr)
        elif platform == 'ILLUMINA' and model.startswith(
                'Illumina Genome Analyzer II'):
            subprocess.run(
                [
                    'java', '-jar', trimmomatic_jar_path, 'SE',
                    path.join(output_prefix, sra_file_name + '_1.fastq'),
                    path.join(output_prefix, 'output.fastq'), 'ILLUMINACLIP:' +
                    get_trimmomatic_adapter_path('TruSeq2-SE.fa') + ':2:30:10',
                    'LEADING:3', 'TRAILING:3', 'SLIDINGWINDOW:4:15',
                    'MINLEN:36', 'TOPHRED33'
                ],
                stdout=f_stdout,
                stderr=f_stderr)
        else:
            # Use adapter file from BBMap for other platforms and models.
            subprocess.run(
                [
                    'java', '-jar', trimmomatic_jar_path, 'SE',
                    path.join(output_prefix, sra_file_name + '_1.fastq'),
                    path.join(output_prefix, 'output.fastq'),
                    'ILLUMINACLIP:' + get_bbmap_adapter_path() + ':2:30:10',
                    'LEADING:3', 'TRAILING:3', 'SLIDINGWINDOW:4:15',
                    'MINLEN:36', 'TOPHRED33'
                ],
                stdout=f_stdout,
                stderr=f_stderr)
        f_stdout.close()
        f_stderr.close()
        print('Aligning ...')
        f_stdout = open(
            path.join(output_prefix, sra_file_name + '.hisat2.log'), 'w')
        f_stderr = open(
            path.join(output_prefix, sra_file_name + '.hisat2.errlog'), 'w')
        subprocess.run(
            [
                get_hisat2_command_path('hisat2-build'), genome,
                path.join(output_prefix, genome_file_name)
            ],
            stdout=f_stdout,
            stderr=f_stderr)
        subprocess.run(
            [
                get_hisat2_command_path('hisat2'), '-x',
                path.join(output_prefix, genome_file_name), '-U',
                path.join(output_prefix, 'output.fastq'), '-S',
                path.join(output_prefix, 'output.sam')
            ],
            stdout=f_stdout,
            stderr=f_stderr)
        f_stdout.close()
        f_stderr.close()
    elif layout == 'PAIRED':
        print('QC ...')
        f_stdout = open(
            path.join(output_prefix, sra_file_name + '_1.fastqc.log'), 'w')
        f_stderr = open(
            path.join(output_prefix, sra_file_name + '_1.fastqc.errlog'), 'w')
        subprocess.run(
            [
                fastqc_path, '--outdir', output_prefix,
                path.join(output_prefix, sra_file_name + '_1.fastq')
            ],
            stdout=f_stdout,
            stderr=f_stderr)
        f_stdout.close()
        f_stderr.close()
        f_stdout = open(
            path.join(output_prefix, sra_file_name + '_2.fastqc.log'), 'w')
        f_stderr = open(
            path.join(output_prefix, sra_file_name + '_2.fastqc.errlog'), 'w')
        subprocess.run(
            [
                fastqc_path, '--outdir', output_prefix,
                path.join(output_prefix, sra_file_name + '_2.fastq')
            ],
            stdout=f_stdout,
            stderr=f_stderr)
        with ZipFile(
                path.join(output_prefix, sra_file_name + '_1_fastqc.zip'),
                'r') as zip_ref:
            zip_ref.extractall(output_prefix)
        with ZipFile(
                path.join(output_prefix, sra_file_name + '_2_fastqc.zip'),
                'r') as zip_ref:
            zip_ref.extractall(output_prefix)
        print('Trimming ...')
        f_stdout = open(
            path.join(output_prefix, sra_file_name + '.trimmomatic.log'), 'w')
        f_stderr = open(
            path.join(output_prefix, sra_file_name + '.trimmomatic.errlog'),
            'w')
        if platform == 'ILLUMINA' and (model.startswith('Illumina HiSeq')
                                       or model.startswith('Illumina MiSeq')):
            subprocess.run(
                [
                    'java', '-jar', trimmomatic_jar_path, 'PE',
                    path.join(output_prefix, sra_file_name + '_1.fastq'),
                    path.join(output_prefix, sra_file_name + '_2.fastq'),
                    path.join(output_prefix, 'output_1.fastq'),
                    path.join(output_prefix, 'output_1_un.fastq'),
                    path.join(output_prefix, 'output_2.fastq'),
                    path.join(output_prefix,
                              'output_2_un.fastq'), 'ILLUMINACLIP:' +
                    get_trimmomatic_adapter_path('TruSeq3-PE.fa') + ':2:30:10',
                    'LEADING:3', 'TRAILING:3', 'SLIDINGWINDOW:4:15',
                    'MINLEN:36', 'TOPHRED33'
                ],
                stdout=f_stdout,
                stderr=f_stderr)
        elif platform == 'ILLUMINA' and model.startswith(
                'Illumina Genome Analyzer II'):
            subprocess.run(
                [
                    'java', '-jar', trimmomatic_jar_path, 'PE',
                    path.join(output_prefix, sra_file_name + '_1.fastq'),
                    path.join(output_prefix, sra_file_name + '_2.fastq'),
                    path.join(output_prefix, 'output_1.fastq'),
                    path.join(output_prefix, 'output_1_un.fastq'),
                    path.join(output_prefix, 'output_2.fastq'),
                    path.join(output_prefix,
                              'output_2_un.fastq'), 'ILLUMINACLIP:' +
                    get_trimmomatic_adapter_path('TruSeq2-PE.fa') + ':2:30:10',
                    'LEADING:3', 'TRAILING:3', 'SLIDINGWINDOW:4:15',
                    'MINLEN:36', 'TOPHRED33'
                ],
                stdout=f_stdout,
                stderr=f_stderr)
        else:
            # use BBTool (BBMerge) to determine the adapter first, then run the Trimmomatic
            f_bbmap_stdout = open(
                path.join(output_prefix, sra_file_name + '.bbmap.log'), 'w')
            f_bbmap_stderr = open(
                path.join(output_prefix, sra_file_name + '.bbmap.errlog'), 'w')
            subprocess.run(
                [
                    get_bbmap_command_path('bbmerge.sh'), 'in1=' + path.join(
                        output_prefix, sra_file_name + '_1.fastq'), 'in2=' +
                    path.join(output_prefix, sra_file_name + '_2.fastq'),
                    'outa=' + path.join(output_prefix, 'adapters.fa')
                ],
                stdout=f_bbmap_stdout,
                stderr=f_bbmap_stderr)
            f_bbmap_stdout.close()
            f_bbmap_stderr.close()
            subprocess.run(
                [
                    'java', '-jar', trimmomatic_jar_path, 'PE',
                    path.join(output_prefix, sra_file_name + '_1.fastq'),
                    path.join(output_prefix, sra_file_name + '_2.fastq'),
                    path.join(output_prefix, 'output_1.fastq'),
                    path.join(output_prefix, 'output_1_un.fastq'),
                    path.join(output_prefix, 'output_2.fastq'),
                    path.join(output_prefix, 'output_2_un.fastq'),
                    'ILLUMINACLIP:' + path.join(output_prefix, 'adapters.fa') +
                    ':2:30:10', 'LEADING:3', 'TRAILING:3',
                    'SLIDINGWINDOW:4:15', 'MINLEN:36', 'TOPHRED33'
                ],
                stdout=f_stdout,
                stderr=f_stderr)
        f_stdout.close()
        f_stderr.close()
        print('Aligning ...')
        f_stdout = open(
            path.join(output_prefix, sra_file_name + '.hisat2-build.log'), 'w')
        f_stderr = open(
            path.join(output_prefix, sra_file_name + '.hisat2-build.errlog'),
            'w')
        subprocess.run(
            [
                get_hisat2_command_path('hisat2-build'), genome,
                path.join(output_prefix, genome_file_name)
            ],
            stdout=f_stdout,
            stderr=f_stderr)
        f_stdout.close()
        f_stderr.close()
        f_stdout = open(
            path.join(output_prefix, sra_file_name + '.hisat2.log'), 'w')
        f_stderr = open(
            path.join(output_prefix, sra_file_name + '.hisat2.errlog'), 'w')
        subprocess.run(
            [
                get_hisat2_command_path('hisat2'), '-x',
                path.join(output_prefix, genome_file_name), '-1',
                path.join(output_prefix, 'output_1.fastq'), '-2',
                path.join(output_prefix, 'output_2.fastq'), '-S',
                path.join(output_prefix, 'output.sam')
            ],
            stdout=f_stdout,
            stderr=f_stderr)
        f_stdout.close()
        f_stderr.close()
    # sort and convert to the bam file
    f_stdout = open(
        path.join(output_prefix, sra_file_name + '.samtools.log'), 'w')
    f_stderr = open(
        path.join(output_prefix, sra_file_name + '.samtools.errlog'), 'w')
    subprocess.run(
        [
            'samtools', 'sort', '-o',
            path.join(output_prefix, 'output.bam'), '-O', 'bam', '-T',
            path.join(output_prefix, 'output'),
            path.join(output_prefix, 'output.sam')
        ],
        stdout=f_stdout,
        stderr=f_stderr)
    f_stdout.close()
    f_stderr.close()
    return (True, '')


def merge_files(files, outdir):  # merge sam files
    print('Combing the sam/bam files ...')
    f_stdout = open(path.join(outdir, 'out.log'), 'a')
    f_stderr = open(path.join(outdir, 'out.errlog'), 'a')
    args = [
        'java', '-jar',
        get_picard_jar_path(), 'MergeSamFiles',
        'O=' + path.join(outdir, 'output.bam')
    ]
    args += ['I=' + f for f in files]
    subprocess.run(args, stdout=f_stdout, stderr=f_stderr)
    print('Finished combining the sam/bam files')


def check_ref_files(ref_path):
    if path.exists(ref_path + '.fai') and path.exists('.dict'):
        return True
    else:
        return False


def read_sam_errors(file_path):
    warns = set()
    errors = set()
    with open(file_path) as f:
        for line in islice(f, 4, None):
            temp = line.split('\t')[0]
            if 'ERROR' in temp:
                errors.add(temp.lstrip('ERROR:'))
            elif 'WARNING' in temp:
                warns.add(temp.lstrip('WARNING:'))
            elif temp == '\n':
                break
    return (errors, warns)


if __name__ == '__main__':
    # parse the arguments, exclude the script name
    args = parse_args(argv[1:])

    # convert many arguments to absolute path
    if not path.isabs(args.outdir):
        args.outdir = path.abspath(args.outdir)
    if not path.isabs(args.input):
        args.input = path.abspath(args.input)
    if not path.isabs(args.genome):
        args.genome = path.abspath(args.genome)

    os.mkdir(path.join(args.outdir, args.name))
    if args.genome.endswith('.gz'):
        new_genome_file_name = path.join(
            args.outdir, args.name,
            path.basename(args.genome).rstrip('.gz'))
        with gzip.open(args.genome, 'rb') as f_in:
            with open(new_genome_file_name, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        args.genome = new_genome_file_name

    with open(args.input) as f:
        col_names = f.readline().rstrip('\n').split('\t')
        run_ind = col_names.index('Run')
        platform_ind = col_names.index('Platform')
        model_ind = col_names.index('Model')
        layout_ind = col_names.index('LibraryLayout')
        download_ind = col_names.index('download_path')
        print('Checking the input tsv file: {}'.format(args.input))
        for ind, name in zip([run_ind, platform_ind, model_ind, layout_ind, download_ind],
                             ['Run', 'Platform', 'Model', 'LibraryLayout', 'download_path']):
            if ind == -1:
                print('{} column is missing in input tsv file.'.format(name))
                exit(1)
        runs = []
        platforms = []
        models = []
        layouts = []
        download_links = []
        for line in f:
            temp = line.rstrip('\n').split('\t')
            runs.append(temp[run_ind])
            platforms.append(temp[platform_ind])
            models.append(temp[model_ind])
            layouts.append(temp[layout_ind])
            download_links.append(temp[download_ind])
    files_for_merge = []
    for run, platform, model, layout, download_link in zip(runs, platforms, models, layouts, download_links):
        print('Processing the file: {}'.format(run))
        if not path.isabs(run):
            run = path.abspath(run)
        run_file_name = path.basename(run)
        return_status, err_message = run_pipeline(
            file=run,
            genome=args.genome,
            outdir=path.join(args.outdir, args.name),
            name=run_file_name,
            layout=layout,
            platform=platform,
            model=model,
            download_link=download_link
            )
        if return_status:
            files_for_merge.append(
                path.join(args.outdir, args.name, run_file_name, 'output.bam'))
        else:
            print(err_message)
    # combine the sam files together and convert to BAM file
    merge_files(files_for_merge, path.join(args.outdir, args.name))
    # handle the downsample
    if args.downsample:
        if not check_ref_files(args.genome):
            print('Creating sequence directory')
            # create the picard dict and samtools index
            file_prefix, _ = path.splitext(args.genome)
            subprocess.run([
                'java', '-jar', get_picard_jar_path(), 'CreateSequenceDictionary',
                'R=' + args.genome, 'O=' + file_prefix + '.dict'
            ])
            print('Creating the index')
            subprocess.run(['samtools', 'faidx', args.genome])
        print('Validating the sam/bam file ...')
        f_stdout = open(
            path.join(args.outdir, args.name, 'check_bam.log'), 'w')
        f_stderr = open(
            path.join(args.outdir, args.name, 'check_bam.errlog'), 'w')
        subprocess.run(
            [
                'java', '-jar', get_picard_jar_path(), 'ValidateSamFile',
                'I=' + path.join(args.outdir, args.name, 'output.bam'),
                'O=' + path.join(args.outdir, args.name, 'validatesam.log'),
                'MAX_RECORDS_IN_RAM=50000',
                'MODE=SUMMARY'
            ],
            stdout=f_stdout,
            stderr=f_stderr)
        errors, _ = read_sam_errors(
            path.join(args.outdir, args.name, 'validatesam.log'))
        # fix missing read groups error
        if 'MISSING_READ_GROUP' in errors:
            f_stdout = open(
                path.join(args.outdir, args.name, 'fix_missing_read_group.log'), 'w')
            f_stderr = open(
                path.join(args.outdir, args.name, 'fix_missing_read_group.errlog'), 'w')
            subprocess.run(
                [
                    'java', '-jar', get_picard_jar_path(),
                    'AddOrReplaceReadGroups',
                    'I=' + path.join(args.outdir, args.name, 'output.bam'),
                    'O=' + path.join(args.outdir, args.name, 'output.bam.temp'),
                    'RGID=output.bam', # read group id is file name
                    'RGLB=unknown', 'RGPL=unknown', 'RGPU=unknown', 'RGSM=unknown',
                    'MAX_RECORDS_IN_RAM=50000'
                ],
                stdout=f_stdout,
                stderr=f_stderr
                )
            os.remove(path.join(args.outdir, args.name, 'output.bam'))
            os.rename(path.join(args.outdir, args.name, 'output.bam.temp'), path.join(args.outdir, args.name, 'output.bam'))
        # TODO: handle other errors and warnings
        print('Start downsampling ...')
        f_stdout = open(
            path.join(args.outdir, args.name, 'build_bam_index.log'), 'w')
        f_stderr = open(
            path.join(args.outdir, args.name, 'build_bam_index.errlog'), 'w')
        subprocess.run(
            [
                'java', '-jar',
                get_picard_jar_path(), 'BuildBamIndex',
                'I=' + path.join(args.outdir, args.name, 'output.bam')
            ],
            stdout=f_stdout,
            stderr=f_stderr)
        f_stdout = open(
            path.join(args.outdir, args.name, 'reduce_coverage.log'), 'w')
        f_stderr = open(
            path.join(args.outdir, args.name, 'reduce_coverage.errlog'), 'w')
        subprocess.run(
            [
                'java', '-jar', get_gatk_jar_path(),
                '-T', 'PrintReads', '-R', args.genome,
                '-I', path.join(args.outdir, args.name, 'output.bam'),
                '-o', path.join(args.outdir, args.name, 'output.reduce.bam'),
                '-dcov', '1', '-U', 'ALLOW_N_CIGAR_READS'
            ],
            stdout=f_stdout,
            stderr=f_stderr)
        print('Finished processing.')
