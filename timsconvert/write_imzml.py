from pyimzml.ImzMLWriter import ImzMLWriter
from timsconvert.maldi.parse_maldi import *


def write_maldi_ims_imzml(data, outdir, outfile, groupby='frame', encoding=0, imzml_mode='processed', centroid=True):
    if data.meta_data['SchemaType'] == 'TDF':
        list_of_scan_dicts = parse_maldi_tdf(data, groupby, encoding, centroid)
    elif data.meta_data['SchemaType'] == 'TSF':
        list_of_scan_dicts = parse_maldi_tsf(data, centroid)

    polarity = list(set(data.frames['Polarity'].values.tolist()))
    if len(polarity) == 1:
        polarity = polarity[0]
        if polarity == '+':
            polarity = 'positive'
        elif polarity == '-':
            polarity = 'negative'
        else:
            polarity = None
    else:
        polarity = None

    writer = ImzMLWriter(os.path.join(outdir, outfile),
                         polarity=polarity,
                         mode=imzml_mode,
                         spec_type=centroid)

    logging.info(get_timestamp() + ':' + 'Writing to .imzML file ' + os.path.join(outdir, outfile) + '...')
    with writer as imzml_file:
        for scan_dict in list_of_scan_dicts:
            imzml_file.addSpectrum(scan_dict['mz_array'],
                                   scan_dict['intensity_array'],
                                   scan_dict['coord'])
