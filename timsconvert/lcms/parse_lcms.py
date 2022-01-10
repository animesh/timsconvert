from timsconvert.utils.timestamp import *
import alphatims.bruker
import alphatims.utils
import sqlite3
import numpy as np
import pandas as pd
import os
import sys
import itertools
import logging


# Function for itertools.groupby() to sort dictionaries based on key.
def key_func_frames(k):
    return k['parent_frame']


# Function for itertools.groupby() to sort dictionaries based on key.
def key_func_scans(k):
    return k['parent_scan']


# Parse MS1 spectrum and output to dictionary containing necessary data.
def parse_lcms_tdf_ms1_scan(scan, frame_num, infile, centroid, ms1_groupby):
    mz_array = scan['mz_values'].values.tolist()
    intensity_array = scan['intensity_values'].values.tolist()

    if len(mz_array) != 0 and len(intensity_array) != 0:
        # Set up .tdf database connection.
        con = sqlite3.connect(os.path.join(infile, 'analysis.tdf'))
        # Get polarity.
        pol_query = 'SELECT * FROM Properties WHERE Frame == ' + str(frame_num)
        pol_query_df = pd.read_sql_query(pol_query, con)
        pol_prop_query = 'SELECT * FROM PropertyDefinitions WHERE PermanentName = "Mode_IonPolarity"'
        pol_prop_query_df = pd.read_sql_query(pol_prop_query, con)
        pol_prop_id = pol_prop_query_df['Id'].values.tolist()[0]
        # Close connection to database.
        con.close()
        # Property 1229 == Mode_IonPolarity; alternatively maybe use 1098 == TOF_IonPolarity?
        polarity_value = list(set(pol_query_df.loc[pol_query_df['Property'] == pol_prop_id]['Value'].values.tolist()))
        if len(polarity_value) == 1:
            polarity_value = polarity_value[0]
            if int(polarity_value) == 0:
                polarity = 'positive scan'
            elif int(polarity_value == 1):
                polarity = 'negative scan'
            else:
                polarity = None
        else:
            polarity = None

        base_peak_index = intensity_array.index(max(intensity_array))
        scan_dict = {'scan_number': None,
                     'mz_array': mz_array,
                     'intensity_array': intensity_array,
                     'scan_type': 'MS1 spectrum',
                     'polarity': polarity,
                     'centroided': centroid,
                     'retention_time': float(list(set(scan['rt_values_min'].values.tolist()))[0]),
                     'total_ion_current': sum(intensity_array),
                     'base_peak_mz': float(mz_array[base_peak_index]),
                     'base_peak_intensity': float(intensity_array[base_peak_index]),
                     'ms_level': 1,
                     'high_mz': float(max(mz_array)),
                     'low_mz': float(min(mz_array)),
                     'parent_frame': 0,
                     'parent_scan': None}

        # Spectrum has single mobility value if grouped by scans (mobility).
        if ms1_groupby == 'scan':
            mobility = list(set(scan['mobility_values'].values.tolist()))
            if len(mobility) == 1:
                scan_dict['mobility'] = mobility[0]
            scan_dict['parent_scan'] = int(list(set(scan['scan_indices'].values.tolist()))[0])
        # Spectrum has array of mobility values if grouped by frame (retention time).
        elif ms1_groupby == 'frame':
            scan_dict['mobility_array'] = scan['mobility_values']
        return scan_dict
    else:
        return None


# Get all MS2 scans. Based in part on alphatims.bruker.save_as_mgf().
def parse_lcms_tdf_ms2_scans(tdf_data, infile, centroid, ms1_groupby, ms2_keep_n_most_abundant_peaks):
    # Check to make sure timsTOF object is valid.
    if tdf_data.acquisition_mode != 'ddaPASEF':
        return None

    # Set up precursor information and get values for precursor indexing.
    (spectrum_indptr,
     spectrum_tof_indices,
     spectrum_intensity_values) = tdf_data.index_precursors(centroiding_window=0,
                                                            keep_n_most_abundant_peaks=ms2_keep_n_most_abundant_peaks)
    mono_mzs = tdf_data.precursors.MonoisotopicMz.values
    average_mzs = tdf_data.precursors.AverageMz.values
    charges = tdf_data.precursors.Charge.values
    charges[np.flatnonzero(np.isnan(charges))] = 0
    charges = charges.astype(np.int64)
    rtinseconds = tdf_data.rt_values[tdf_data.precursors.Parent.values]
    intensities = tdf_data.precursors.Intensity.values
    mobilities = tdf_data.mobility_values[tdf_data.precursors.ScanNumber.values.astype(np.int64)]
    parent_frames = tdf_data.precursors.Parent.values
    parent_scans = np.floor(tdf_data.precursors.ScanNumber.values)

    # Set up .tdf database connection.
    con = sqlite3.connect(os.path.join(infile, 'analysis.tdf'))

    list_of_scan_dicts = []
    for index in alphatims.utils.progress_callback(range(1, tdf_data.precursor_max_index)):
        start = spectrum_indptr[index]
        end = spectrum_indptr[index + 1]

        # Remove MS2 scan if empty.
        if tdf_data.mz_values[spectrum_tof_indices[start:end]].size != 0 or spectrum_intensity_values[start:end] != 0:
            if not np.isnan(mono_mzs[index - 1]):
                # Get isolation width and collision energy from Properties table in .tdf file.
                iso_query = 'SELECT * FROM PasefFrameMsMsInfo WHERE Precursor = ' + str(index) +\
                        ' GROUP BY Precursor, IsolationMz, IsolationWidth, ScanNumBegin, ScanNumEnd'
                iso_query_df = pd.read_sql_query(iso_query, con)
                # Check to make sure there's only one hit. Exit with error if not.
                if iso_query_df.shape[0] != 1:
                    logging.info(get_timestamp() + ':' + 'PasefFrameMsMsInfo Precursor ' + str(index) +
                                 ' dataframe has more than one row.')
                    sys.exit(1)
                collision_energy = int(iso_query_df['CollisionEnergy'].values.tolist()[0])
                # note: isolation widths are slightly off from what is given in alphatims dataframes.
                half_isolation_width = float(iso_query_df['IsolationWidth'].values.tolist()[0]) / 2
                # Get polarity and activation.
                pol_query = 'SELECT * FROM PasefFrameMsMsInfo WHERE Precursor = ' + str(index)
                pol_query_df = pd.read_sql_query(pol_query, con)
                pol_query_2 = 'SELECT * FROM Properties WHERE Frame BETWEEN ' +\
                         str(min(pol_query_df['Frame'].values.tolist())) + ' AND ' +\
                         str(max(pol_query_df['Frame'].values.tolist()))
                pol_query_df_2 = pd.read_sql_query(pol_query_2, con)
                pol_prop_query = 'SELECT * FROM PropertyDefinitions WHERE PermanentName = "Mode_IonPolarity"'
                pol_prop_query_df = pd.read_sql_query(pol_prop_query, con)
                pol_prop_id = pol_prop_query_df['Id'].values.tolist()[0]
                # Property 1229 == Mode_IonPolarity; alternatively maybe use 1098 == TOF_IonPolarity?
                polarity_value = list(set(pol_query_df_2.loc[pol_query_df_2['Property'] == pol_prop_id]['Value'].values.tolist()))
                if len(polarity_value) == 1:
                    polarity_value = polarity_value[0]
                    if int(polarity_value) == 0:
                        polarity = 'positive scan'
                    elif int(polarity_value == 1):
                        polarity = 'negative scan'
                    else:
                        polarity = None
                else:
                    polarity = None
                # Property 1584 == MSMS_ActivationMode_Act; alternatively, maybe use 1640 == MSMSAuto_FragmentationMode?
                '''
                activation_value = list(set(pol_query_df_2.loc[pol_query_df_2['Property'] == 1584]['Value'].values.tolist()))
                if len(activation_value) == 1:
                    activation_value = activation_value[0]
                    if int(activation_value) == 0:
                        if int(collision_energy) <= 1000:
                            activation = 'low-energy collision-induced dissociation'
                        elif int(collision_energy) > 1000:
                            activation = 'collision-induced dissociation'
                    elif int(activation_value) == 1:
                        activation = 'electron transfer dissociation'
                '''

                scan_dict = {'scan_number': None,
                             'mz_array': tdf_data.mz_values[spectrum_tof_indices[start:end]],
                             'intensity_array': spectrum_intensity_values[start:end],
                             'scan_type': 'MSn spectrum',
                             'polarity': polarity,
                             'centroided': centroid,
                             'retention_time': float(rtinseconds[index - 1] / 60),  # in min
                             'total_ion_current': sum(spectrum_intensity_values[start:end]),
                             'ms_level': 2,
                             'target_mz': average_mzs[index - 1],
                             'isolation_lower_offset': half_isolation_width,
                             'isolation_upper_offset': half_isolation_width,
                             'selected_ion_mz': float(mono_mzs[index - 1]),
                             'selected_ion_intensity': float(intensities[index - 1]),
                             'selected_ion_mobility': float(mobilities[index - 1]),
                             'charge_state': int(charges[index - 1]),
                             #'activation': activation,
                             'collision_energy': collision_energy,
                             'parent_frame': parent_frames[index - 1],
                             'parent_scan': int(parent_scans[index - 1])}

                # Get base peak information.
                if spectrum_intensity_values[start:end].size != 0:
                    base_peak_index = spectrum_intensity_values[start:end].argmax()
                    scan_dict['base_peak_mz'] = float(tdf_data.mz_values[spectrum_tof_indices[start:end]]
                                                      [base_peak_index])
                    scan_dict['base_peak_intensity'] = float(spectrum_intensity_values[base_peak_index])

                # Get high and low spectrum m/z values.
                if tdf_data.mz_values[spectrum_tof_indices[start:end]].size != 0:
                    scan_dict['high_mz'] = float(max(tdf_data.mz_values[spectrum_tof_indices[start:end]]))
                    scan_dict['low_mz'] = float(min(tdf_data.mz_values[spectrum_tof_indices[start:end]]))

                list_of_scan_dicts.append(scan_dict)

    # Close connection to database.
    con.close()

    ms2_scans_dict = {}
    # Loop through frames.
    for key, value in itertools.groupby(list_of_scan_dicts, key_func_frames):
        if ms1_groupby == 'scan':
            # Loop through scans.
            for key2, value2 in itertools.groupby(list(value), key_func_scans):
                ms2_scans_dict['f' + str(key) + 's' + str(key2)] = list(value2)
        elif ms1_groupby == 'frame':
            ms2_scans_dict[key] = list(value)

    return ms2_scans_dict


# Extract all scan information including acquisition parameters, m/z, intensity, and mobility arrays/values
# from dataframes for each scan.
def parse_lcms_tdf(tdf_data, ms1_frames, infile, centroid, ms2_only, ms1_groupby, ms2_keep_n_most_abundant_peaks):
    # Get all MS2 scans into dictionary.
    # keys == parent scan
    # values == list of scan dicts containing all the MS2 product scans for a given parent scan
    logging.info(get_timestamp() + ':' + 'Parsing LC-TIMS-MS/MS MS2 spectra.')
    ms2_scans_dict = parse_lcms_tdf_ms2_scans(tdf_data, infile, centroid, ms1_groupby, ms2_keep_n_most_abundant_peaks)

    # Get all MS1 scans into dictionary.
    logging.info(get_timestamp() + ':' + 'Parsing LC-TIMS-MS MS1 spectra.')
    ms1_scans_dict = {}
    for frame_num in ms1_frames:
        if ms1_groupby == 'scan':
            ms1_scans = sorted(list(set(tdf_data[frame_num]['scan_indices'])))
            for scan_num in ms1_scans:
                parent_scan = tdf_data[frame_num, scan_num].sort_values(by='mz_values')
                if ms2_only == False:
                    ms1_scan = parse_lcms_tdf_ms1_scan(parent_scan, frame_num, infile, centroid, ms1_groupby)
                    ms1_scans_dict['f' + str(frame_num) + 's' + str(scan_num)] = ms1_scan
                elif ms2_only == True:
                    ms1_scans_dict['f' + str(frame_num) + 's' + str(scan_num)] = None
        elif ms1_groupby == 'frame':
            parent_scan = tdf_data[frame_num].sort_values(by='mz_values')
            if ms2_only == False:
                ms1_scan = parse_lcms_tdf_ms1_scan(parent_scan, frame_num, infile, centroid, ms1_groupby)
                ms1_scans_dict[frame_num] = ms1_scan
            elif ms2_only == True:
                ms1_scans_dict[frame_num] = None

    return ms1_scans_dict, ms2_scans_dict


if __name__ == '__main__':
    logger = logging.getLogger(__name__)
