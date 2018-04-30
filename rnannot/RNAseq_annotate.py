import os
from os import path
from parser import parse_args
from sys import argv, exit
from utils import get_trimmomatic_jar_path, get_fastqc_path, get_trimmomatic_adapter_path, get_hisat2_command_path, get_bbmap_command_path, get_bbmap_adapter_path
import subprocess
from zipfile import ZipFile
import gzip
import shutil


def run_pipeline(file, genome, outdir, name, layout, platform, model):
    # create the output folder
    output_prefix = path.join(outdir, name)
    os.mkdir(output_prefix)
    
    # decompress the gz file, becasue some of tools don't accerpt .gz compressed files
    if genome.endswith('.gz'):
        new_genome_file_name = path.join(output_prefix, path.basename(genome).rstrip('.gz'))
        with gzip.open(genome, 'rb') as f_in:
            with open(new_genome_file_name, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        genome =  new_genome_file_name
    sra_file_name = path.basename(file)
    genome_file_name = path.basename(genome)

    # convert SRA file to fastq file(s)
    print('Unpacking the SRA file: {} ...'.format(file))
    subprocess.run(['fastq-dump', '--split-files', '-O', output_prefix, file])

    # Check if the SRA file is correct or not first 
    if layout == 'PAIRED' and (not path.exists(path.join(output_prefix, sra_file_name + '_1.fastq')) or not path.exists(path.join(output_prefix, sra_file_name + '_1.fastq'))):
        return (False, "run {} doesn't have paired data. It's not processed.".format(run))
    
    # Run FastQC first
    # Then, use Trimmomatic to do trimming
    # In the last step, perfom the alignment using HISAT2
    fastqc_path = get_fastqc_path()
    trimmomatic_jar_path = get_trimmomatic_jar_path()
    if layout == 'SINGLE':
        print('QC and trimming ...')
        f_stdout = open(path.join(output_prefix, sra_file_name + '_1.fastqc.log'), 'w')
        f_stderr = open(path.join(output_prefix, sra_file_name + '_1.fastqc.errlog'), 'w')
        subprocess.run([fastqc_path, '--outdir', output_prefix, path.join(output_prefix, sra_file_name + '_1.fastq')], stdout=f_stdout, stderr=f_stderr)
        with ZipFile(path.join(output_prefix, sra_file_name + '_1_fastqc.zip'), 'r') as zip_ref:
            zip_ref.extractall(output_prefix)
        f_stdout = open(path.join(output_prefix, sra_file_name + '.trimmomatic.log'), 'w')
        f_stderr = open(path.join(output_prefix, sra_file_name + '.trimmomatic.errlog'), 'w')
        if platform == 'ILLUMINA' and (model.startswith('Illumina HiSeq') or model.startswith('Illumina MiSeq')):
            subprocess.run([
                    'java', '-jar', trimmomatic_jar_path,
                    'SE', path.join(output_prefix, sra_file_name + '_1.fastq'),
                    path.join(output_prefix, 'output.fastq'),
                    'ILLUMINACLIP:' + get_trimmomatic_adapter_path('TruSeq3-SE.fa') + ':2:30:10',
                    'LEADING:3',
                    'TRAILING:3',
                    'SLIDINGWINDOW:4:15',
                    'MINLEN:36',
                    'TOPHRED33'
                ],
                stdout=f_stdout,
                stderr=f_stderr)
        elif platform == 'ILLUMINA' and model.startswith('Illumina Genome Analyzer II'):
            subprocess.run([
                'java', '-jar', trimmomatic_jar_path,
                    'SE', path.join(output_prefix, sra_file_name + '_1.fastq'),
                    path.join(output_prefix, 'output.fastq'),
                    'ILLUMINACLIP:' + get_trimmomatic_adapter_path('TruSeq2-SE.fa') + ':2:30:10',
                    'LEADING:3',
                    'TRAILING:3',
                    'SLIDINGWINDOW:4:15',
                    'MINLEN:36',
                    'TOPHRED33'
                ],
                stdout=f_stdout,
                stderr=f_stderr)
        else: 
            # Use adapter file from BBMap for other platforms and models.
            # TODO: Another strategy can be used is to guess adapter from FastQC output
            subprocess.run([
                    'java', '-jar', trimmomatic_jar_path,
                    'SE', path.join(output_prefix, sra_file_name + '_1.fastq'),
                    path.join(output_prefix, 'output.fastq'),
                    'ILLUMINACLIP:' + get_bbmap_adapter_path() + ':2:30:10',
                    'LEADING:3',
                    'TRAILING:3',
                    'SLIDINGWINDOW:4:15',
                    'MINLEN:36',
                    'TOPHRED33'
                ],
                stdout=f_stdout,
                stderr=f_stderr)
        print('Aligning ...')
        f_stdout = open(path.join(output_prefix, sra_file_name + '.hisat2.log'), 'w')
        f_stderr = open(path.join(output_prefix, sra_file_name + '.hisat2.errlog'), 'w')
        subprocess.run([get_hisat2_command_path('hisat2-build'), genome, path.join(output_prefix, genome_file_name)])
        subprocess.run([
                get_hisat2_command_path('hisat2'),
                '-x', path.join(output_prefix, genome_file_name),
                '-U', path.join(output_prefix, 'output.fastq'),
                '-S', path.join(output_prefix, 'output.sam')
            ],
            stdout=f_stdout,
            stderr=f_stderr
        )
    elif layout == 'PAIRED':
        print('QC and trimming ...')
        f_stdout = open(path.join(output_prefix, sra_file_name + '_1.fastqc.log'), 'w')
        f_stderr = open(path.join(output_prefix, sra_file_name + '_1.fastqc.errlog'), 'w')
        subprocess.run([fastqc_path, '--outdir', output_prefix, path.join(output_prefix, sra_file_name + '_1.fastq')], stdout=f_stdout, stderr=f_stderr)
        f_stdout = open(path.join(output_prefix, sra_file_name + '_2.fastqc.log'), 'w')
        f_stderr = open(path.join(output_prefix, sra_file_name + '_2.fastqc.errlog'), 'w')
        subprocess.run([fastqc_path, '--outdir', output_prefix, path.join(output_prefix, sra_file_name + '_2.fastq')], stdout=f_stdout, stderr=f_stderr)
        with ZipFile(path.join(output_prefix, sra_file_name + '_1_fastqc.zip'), 'r') as zip_ref:
            zip_ref.extractall(output_prefix)
        with ZipFile(path.join(output_prefix, sra_file_name + '_2_fastqc.zip'), 'r') as zip_ref:
            zip_ref.extractall(output_prefix)
        f_stdout = open(path.join(output_prefix, sra_file_name + '.trimmomatic.log'), 'w')
        f_stderr = open(path.join(output_prefix, sra_file_name + '.trimmomatic.errlog'), 'w')
        if platform == 'ILLUMINA' and (model.startswith('Illumina HiSeq') or model.startswith('Illumina MiSeq')): 
            subprocess.run([
                    'java', '-jar', trimmomatic_jar_path,
                    'PE',
                    path.join(output_prefix, sra_file_name + '_1.fastq'),
                    path.join(output_prefix, sra_file_name + '_2.fastq'),
                    path.join(output_prefix, 'output_1.fastq'),
                    path.join(output_prefix, 'output_2.fastq'),
                    'ILLUMINACLIP:' + get_trimmomatic_adapter_path('TruSeq3-PE.fa') + ':2:30:10',
                    'LEADING:3',
                    'TRAILING:3',
                    'SLIDINGWINDOW:4:15',
                    'MINLEN:36',
                    'TOPHRED33'
                ],
                stdout=f_stdout,
                stderr=f_stderr
            )
        elif platform == 'ILLUMINA' and model.startswith('Illumina Genome Analyzer II'):
            subprocess.run([
                    'java', '-jar', trimmomatic_jar_path,
                    'PE',
                    path.join(output_prefix, sra_file_name + '_1.fastq'),
                    path.join(output_prefix, sra_file_name + '_2.fastq'),
                    path.join(output_prefix, 'output_1.fastq'),
                    path.join(output_prefix, 'output_2.fastq'),
                    'ILLUMINACLIP:' + get_trimmomatic_adapter_path('TruSeq2-PE.fa') + ':2:30:10',
                    'LEADING:3',
                    'TRAILING:3',
                    'SLIDINGWINDOW:4:15',
                    'MINLEN:36',
                    'TOPHRED33'
                ],
                stdout=f_stdout,
                stderr=f_stderr
            )
        else:
            # use BBTool (BBMerge) to determine the adapter first, then run the Trimmomatic
            f_bbmap_stdout = open(path.join(output_prefix, sra_file_name + '_2.bbmap.log'), 'w')
            f_bbmap_stderr = open(path.join(output_prefix, sra_file_name + '_2.bbmap.errlog'), 'w')
            subprocess.run([
                    get_bbmap_command_path('bbmerge.sh'),
                    'in1=' + path.join(output_prefix, sra_file_name + '_1.fastq'),
                    'in2=' + path.join(output_prefix, sra_file_name + '_2.fastq'),
                    'outa=' + path.join(output_prefix, 'adapters.fa')
                ],
                stdout=f_bbmap_stdout,
                stderr=f_bbmap_stderr
            )
            subprocess.run([
                    'java', '-jar', trimmomatic_jar_path,
                    'PE',
                    path.join(output_prefix, sra_file_name + '_1.fastq'),
                    path.join(output_prefix, sra_file_name + '_2.fastq'),
                    path.join(output_prefix, 'output_1.fastq'),
                    path.join(output_prefix, 'output_2.fastq'),
                    'ILLUMINACLIP:' + path.join(output_prefix, 'adapters.fa') + ':2:30:10',
                    'LEADING:3',
                    'TRAILING:3',
                    'SLIDINGWINDOW:4:15',
                    'MINLEN:36',
                    'TOPHRED33'
                ],
                stdout=f_stdout,
                stderr=f_stderr
            )
        print('Aligning ...')
        subprocess.run([get_hisat2_command_path('hisat2-build'), genome, path.join(output_prefix, genome_file_name)])
        f_stdout = open(path.join(output_prefix, sra_file_name + '.hisat2.log'), 'w')
        f_stderr = open(path.join(output_prefix, sra_file_name + '.hisat2.errlog'), 'w')
        subprocess.run([
                get_hisat2_command_path('hisat2'),
                '-x', path.join(output_prefix, genome_file_name),
                '-1', path.join(output_prefix, 'output_1.fastq'),
                '-2', path.join(output_prefix, 'output_2.fastq'),
                '-S', path.join(output_prefix, 'output.sam')
            ],
            stdout=f_stdout,
            stderr=f_stderr
        )
    # sort and convert to the bam file
    f_stdout = open(path.join(output_prefix, sra_file_name + '.samtools.log'), 'w')
    f_stderr = open(path.join(output_prefix, sra_file_name + '.samtools.errlog'), 'w')
    subprocess.run([
            'samtools', 'sort',
            '-o', path.join(output_prefix, 'output.bam'),
            '-O', 'bam',
            '-T', path.join(output_prefix, 'output'),
            path.join(output_prefix, 'output.sam')
        ],
        stdout=f_stdout,
        stderr=f_stderr
    )
    return (True, '')


def merge_files(files, outdir):  # merge sam files
    f_stdout = open(path.join(outdir, 'out.log'), 'w')
    f_stderr = open(path.join(outdir, 'out.errlog'), 'w')
    args = ['samtools', 'merge', path.join(outdir, 'output.bam')]
    args.extend(files) 
    subprocess.run(args)


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

    with open(args.input) as f:
        col_names = f.readline().rstrip('\n').split('\t')
        run_ind = col_names.index('Run')
        platform_ind = col_names.index('Platform')
        model_ind = col_names.index('Model')
        layout_ind = col_names.index('LibraryLayout')
        print('Checking the input tsv file: {}'.format(args.input))
        for ind, name in zip([run_ind, platform_ind, model_ind, layout_ind], ['Run', 'Platform', 'Model', 'LibraryLayout']):
            if ind == -1:
                print('{} column is missing in input tsv file.'.format(name))
                exit(1)
        runs = []
        platforms = []
        models = []
        layouts = []
        for line in f:
            temp = line.rstrip('\n').split('\t')
            runs.append(temp[run_ind])
            platforms.append(temp[platform_ind])
            models.append(temp[model_ind])
            layouts.append(temp[layout_ind])
    os.mkdir(path.join(args.outdir, args.name))
    files_for_merge = []
    for run, platform, model, layout in zip(runs, platforms, models, layouts):
        print('Processing the file: {}'.format(run))
        if not path.isabs(run):
            run = path.abspath(run)
        run_file_name = path.basename(run)
        return_status, err_message = run_pipeline(file=run, genome=args.genome, outdir=path.join(args.outdir, args.name), name=run_file_name, layout=layout, platform=platform, model=model)
        if return_status:
            files_for_merge.append(path.join(args.outdir, args.name, run_file_name, 'output.bam'))
        else:
            print(err_message)
    # combine the sam files together and conver to BAM file
    print('Combing the sam files ...')
    merge_files(files_for_merge, path.join(args.outdir, args.name))

