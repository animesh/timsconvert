import alphatims.bruker
from lxml import etree as et
import os
import itertools


# Function for itertools.groupby() to sort dictionaries based on key.
def key_func(k):
    return k['parent_frame']


# Check method for PASEF NumRampsPerCycle
# From microTOFQImpacTemAcquisition.method XML file.
def get_method_info(input_filename):
    # Get method file path.
    for dirpath, dirnames, filenames in os.walk(input_filename):
        for dirname in dirnames:
            if os.path.splitext(dirname)[1].lower() == '.m':
                method_file = os.path.join(dirpath, dirname, 'microTOFQImpacTemAcquisition.method')

    # Open XML file.
    method_data = et.parse(method_file).getroot()
    method_params = {}
    # Get get number of ramps per cycle.
    method_params['num_ramps_per_cycle'] = int(method_data.xpath('//para_int[@permname="MSMS_Pasef_NumRampsPerCycle"]')[0].attrib['value'])
    # polarity is hardcoded for now, need to find where to get that parameter
    method_params['polarity'] = 'positive scan'
    return method_params


# will need to figure out how to centroid data later; only outputs profile for now
def parse_ms1_scan(scan, method_params, centroided=False):
    base_peak_row = scan.sort_values(by='intensity_values', ascending=False).iloc[0]
    scan_dict = {'scan_number': 0,
                 'mz_array': scan['mz_values'].values.tolist(),
                 'intensity_array': scan['intensity_values'].values.tolist(),
                 'mobility_array': scan['mobility_values'].values.tolist(),
                 'scan_type': 'MS1 spectrum',
                 'polarity': method_params['polarity'],
                 'centroided': centroided,
                 'retention_time': float(list(set(scan['rt_values_min'].values.tolist()))[0]),
                 'total_ion_current': sum(scan['intensity_values'].values.tolist()),
                 'base_peak_mz': float(base_peak_row['mz_values']),
                 'base_peak_intensity': float(base_peak_row['intensity_values']),
                 'ms_level': 1,
                 'high_mz': float(max(scan['mz_values'].values.tolist())),
                 'low_mz': float(min(scan['mz_values'].values.tolist())),
                 'parent_frame': 0}
    return scan_dict


# Get all MS2 scans.
def parse_ms2_scans(raw_data, method_params, overwrite=False, centroided=True,
                   centroiding_window=5, keep_n_most_abundant_peaks=-1):
    # Check to make sure timsTOF object is valid.
    if raw_data.acquisition_mode != 'ddaPASEF':
        return None

    (spectrum_indptr,
     spectrum_tof_indices,
     spectrum_intensity_values) = raw_data.index_precursors(centroiding_window=centroiding_window,
                                                            keep_n_most_abundant_peaks=keep_n_most_abundant_peaks)
    mono_mzs = raw_data.precursors.MonoisotopicMz.values
    average_mzs = raw_data.precursors.AverageMz.values
    charges = raw_data.precursors.Charge.values
    charges[np.flatnonzero(np.isnan(charges))] = 0
    charges = charges.astype(np.int64)
    rtinseconds = raw_data.rt_values[raw_data.precursors.Parent.values]
    intensities = raw_data.precursors.Intensity.values
    mobilities = raw_data.mobility_values[raw_data.precursors.ScanNumber.values.astype(np.int64)]
    quad_mz_values = raw_data.quad_mz_values[raw_data.precursors.ScanNumber.values.astype(np.int64)]
    parent_frames = raw_data.precursors.Parent.values

    list_of_scan_dicts = []
    for index in alphatims.utils.progress_callback(range(1, raw_data.precursor_max_index)):
        start = spectrum_indptr[index]
        end = spectrum_indptr[index + 1]

        # Remove MS2 scan if empty.
        if raw_data.mz_values[spectrum_tof_indices[start:end]].size != 0 or spectrum_intensity_values[start:end] != 0:
            if not np.isnan(mono_mzs[index - 1]):
                scan_dict = {'scan_number': 0,
                             'mz_array': raw_data.mz_values[spectrum_tof_indices[start:end]],
                             'intensity_array': spectrum_intensity_values[start:end],
                             # 'mobility_array': scan['mobility_values'].values.tolist(),  # no mobility array in MS2
                             'scan_type': 'MSn spectrum',
                             'polarity': method_params['polarity'],
                             'centroided': centroided,
                             'retention_time': float(rtinseconds[index - 1] / 60),  # in min
                             'total_ion_current': sum(spectrum_intensity_values[start:end]),
                             'ms_level': 2,
                             'target_mz': average_mzs[index - 1],
                             'isolation_lower_offset': float(quad_mz_values[index - 1][0]),
                             'isolation_upper_offset': float(quad_mz_values[index - 1][1]),
                             'selected_ion_mz': float(mono_mzs[index - 1]),
                             'selected_ion_intensity': float(intensities[index - 1]),
                             'selected_ion_mobility': float(mobilities[index - 1]),
                             'charge_state': int(charges[index - 1]),
                             'collision_energy': 20,  # hard coded for now
                             'parent_frame': parent_frames[index - 1]}

                if spectrum_intensity_values[start:end].size != 0:
                    base_peak_index = spectrum_intensity_values[start:end].argmax()
                    scan_dict['base_peak_mz'] = float(raw_data.mz_values[spectrum_tof_indices[start:end]][base_peak_index])
                    scan_dict['base_peak_intensity'] = float(spectrum_intensity_values[base_peak_index])

                if raw_data.mz_values[spectrum_tof_indices[start:end]].size != 0:
                    scan_dict['high_mz'] = float(max(raw_data.mz_values[spectrum_tof_indices[start:end]]))
                    scan_dict['low_mz'] = float(min(raw_data.mz_values[spectrum_tof_indices[start:end]]))

                list_of_scan_dicts.append(scan_dict)

    ms2_scans_dict = {}
    for key, value in itertools.groupby(list_of_scan_dicts, key_func):
        ms2_scans_dict[key] = list(value)

    return ms2_scans_dict


# Extract all scan information including acquisition parameters, m/z, intensity, and mobility arrays/values
# from dataframes for each scan.
def parse_raw_data(raw_data, ms1_frames, input_filename, output_filename):
    # Get method parameters.
    method_params = get_method_info(input_filename)

    # Get all MS2 scans into dictionary.
    # keys == parent scan
    # values == list of scan dicts containing all the MS2 product scans for a given parent scan
    ms2_scans = parse_ms2_scans(raw_data, method_params, centroiding_window=1)

    ms1_scans = {}
    for frame_num in ms1_frames:
        parent_scan = raw_data[frame_num].sort_values(by='mz_values')
        ms1_scans[frame_num] = parse_ms1_scan(parent_scan, method_params)

    return ms1_scans, ms2_scans