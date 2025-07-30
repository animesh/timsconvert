#include <iostream>
#include <string>
#include <iomanip>
#include <vector>
#include <fstream>
#include <map>
#include <unordered_map>
#include <sstream>
#include <algorithm>

#include "CppSQLite3.h" //https://github.com/neosmart/CppSQLite
#include "timsdata_cpp.h" 

#define OUTPUT_PRECISION 8
#define OUTPUT_WIDTH 9

struct FrameInfo {
    int id;
    double time;
    int numScans;
    int msMsType;
};

struct PrecursorInfo {
    double mz;
    int charge;
    double intensity;
};

struct PasefInfo {
    int frame;
    int scanBegin;
    int scanEnd;
    double collisionEnergy;
    int precursorId;
};

void processAllFrames(timsdata::TimsData& data, CppSQLite3DB& db, 
                     const std::vector<FrameInfo>& frames,
                     const std::unordered_map<int, PrecursorInfo>& precursors,
                     const std::unordered_map<int, std::vector<PasefInfo>>& pasefData,
                     std::ofstream& mgfFile, std::ofstream* ms1File);

int main(int argc, char* argv[])
{
    if(argc < 2 || argc > 3)
    {
        std::cerr << "Usage:" << std::endl;
        std::cerr << argv[0] << " <TDF .d directory> [-ms1]" << std::endl;
        std::cerr << "  -ms1: Also extract MS1 data (optional)" << std::endl;
        return -1;
    }
    
    bool extractMS1 = false;
    std::string tdfDirectory;
    
    // Parse command line arguments
    for (int i = 1; i < argc; i++) {
        std::string arg(argv[i]);
        if (arg == "-ms1") {
            extractMS1 = true;
        } else if (arg[0] != '-') {
            tdfDirectory = arg;
        } else {
            std::cerr << "Unknown option: " << arg << std::endl;
            return -1;
        }
    }
    
    if (tdfDirectory.empty()) {
        std::cerr << "Error: TDF directory not specified" << std::endl;
        return -1;
    }

    std::cout.precision(OUTPUT_PRECISION);

    std::string tdfFile = tdfDirectory + "/analysis.tdf";

    try
    {
        // Open the binary file
        timsdata::TimsData data(tdfDirectory);  // NOTE: UTF-8 conversion needed here!

        // Open the database
        CppSQLite3DB db;
        db.open(tdfFile.c_str());  // NOTE: UTF-8 conversion needed here!

        // Open output files
        std::string mgfFile = tdfDirectory + "_msms.mgf";
        std::ofstream mgfOutput(mgfFile);
        
        std::ofstream ms1Output;
        std::string ms1File;
        if (extractMS1) {
            ms1File = tdfDirectory + "_ms1.txt";
            ms1Output.open(ms1File);
            if (!ms1Output.is_open()) {
                std::cerr << "Error: Could not open MS1 output file" << std::endl;
                return -1;
            }
        }
        
        if (!mgfOutput.is_open()) {
            std::cerr << "Error: Could not open MGF output file" << std::endl;
            return -1;
        }

        std::cout << "Loading metadata..." << std::endl;

        // STEP 1: Load all frame information at once
        std::vector<FrameInfo> frames;
        auto frameQuery = db.execQuery("SELECT Id, Time, NumScans, MsMsType FROM Frames ORDER BY Id;");
        while (!frameQuery.eof()) {
            FrameInfo frame;
            frame.id = frameQuery.getIntField("Id");
            frame.time = frameQuery.getFloatField("Time");
            frame.numScans = frameQuery.getIntField("NumScans");
            frame.msMsType = frameQuery.getIntField("MsMsType");
            frames.push_back(frame);
            frameQuery.nextRow();
        }

        // STEP 2: Load all precursor information at once
        std::unordered_map<int, PrecursorInfo> precursors;
        auto precursorQuery = db.execQuery("SELECT Id, MonoisotopicMz, Charge, Intensity FROM Precursors;");
        while (!precursorQuery.eof()) {
            int id = precursorQuery.getIntField("Id");
            PrecursorInfo prec;
            prec.mz = precursorQuery.getFloatField("MonoisotopicMz");
            prec.charge = precursorQuery.getIntField("Charge");
            prec.intensity = precursorQuery.getFloatField("Intensity");
            precursors[id] = prec;
            precursorQuery.nextRow();
        }

        // STEP 3: Load all PASEF information at once, grouped by frame
        std::unordered_map<int, std::vector<PasefInfo>> pasefData;
        auto pasefQuery = db.execQuery("SELECT Frame, ScanNumBegin, ScanNumEnd, CollisionEnergy, Precursor FROM PasefFrameMsMsInfo ORDER BY Frame;");
        while (!pasefQuery.eof()) {
            PasefInfo pasef;
            pasef.frame = pasefQuery.getIntField("Frame");
            pasef.scanBegin = pasefQuery.getIntField("ScanNumBegin");
            pasef.scanEnd = pasefQuery.getIntField("ScanNumEnd");
            pasef.collisionEnergy = pasefQuery.getFloatField("CollisionEnergy");
            pasef.precursorId = pasefQuery.getIntField("Precursor");
            pasefData[pasef.frame].push_back(pasef);
            pasefQuery.nextRow();
        }

        std::cout << "# TDF file " << tdfDirectory << " contains " << frames.size() << " frames." << std::endl;
        std::cout << "# Loaded " << precursors.size() << " precursors and " << pasefData.size() << " MS/MS frames." << std::endl;
        std::cout << "# MS/MS data written to: " << mgfFile << std::endl;
        if (extractMS1) {
            std::cout << "# MS1 data written to: " << ms1File << std::endl;
        }
        std::cout << std::endl;

        // Write headers
        if (extractMS1) {
            ms1Output << "# MS1 spectra from TDF file: " << tdfDirectory << std::endl;
            ms1Output << "# ZERO-FILTER ONLY - 10th scan sampling with zero intensity filtering" << std::endl;
            ms1Output << "# Format: Frame_ID RT_seconds Scan_Number m/z Intensity Mobility" << std::endl;
            ms1Output << std::endl;
        }

        mgfOutput << "# MS/MS spectra from TDF file: " << tdfDirectory << std::endl;
        mgfOutput << "# ZERO-FILTER ONLY - Remove only zero intensity peaks, keep all peaks per spectrum" << std::endl;
        mgfOutput << "# MGF format for protein identification" << std::endl;
        mgfOutput << std::endl;

        // STEP 4: Process all frames efficiently
        processAllFrames(data, db, frames, precursors, pasefData, mgfOutput, extractMS1 ? &ms1Output : nullptr);

        if (extractMS1) {
            ms1Output.close();
        }
        mgfOutput.close();
        
        std::cout << "Processing completed!" << std::endl;
    }
    catch(const CppSQLite3Exception& e)
    {
        std::cerr << "CppSQLite3Exception: " << e.errorMessage() << std::endl;
    }
    catch(const std::exception& e)
    {
        std::cerr << "Exception: " << e.what() << std::endl;
    }

	return 0;
}


void processAllFrames(timsdata::TimsData& data, CppSQLite3DB& db, 
                     const std::vector<FrameInfo>& frames,
                     const std::unordered_map<int, PrecursorInfo>& precursors,
                     const std::unordered_map<int, std::vector<PasefInfo>>& pasefData,
                     std::ofstream& mgfFile, std::ofstream* ms1File)
{
    int ms1Count = 0;
    int ms2Count = 0;
    int totalFrames = frames.size();
    int skippedPrecursors = 0;  // Track skipped precursors with invalid m/z
    
    // Set buffer sizes for faster I/O
    static char mgfBuffer[4*1024*1024];  // 4MB buffer
    mgfFile.rdbuf()->pubsetbuf(mgfBuffer, sizeof(mgfBuffer));
    
    static char ms1Buffer[4*1024*1024];  // 4MB buffer for MS1 if needed
    if (ms1File) {
        ms1File->rdbuf()->pubsetbuf(ms1Buffer, sizeof(ms1Buffer));
    }
    
    // Pre-allocate reusable containers with larger initial capacity
    std::vector<double> mobilityVec(1);
    std::vector<double> scanVec(1);
    std::vector<double> xAxisMasses;
    std::vector<double> indices;
    std::vector<std::pair<double, double>> peaks;
    xAxisMasses.reserve(2000);  // Pre-reserve space
    indices.reserve(2000);
    peaks.reserve(5000);
    
    // Use stringstreams for batch output to reduce I/O calls
    std::ostringstream mgfBuffer_str;
    std::ostringstream ms1Buffer_str;
    
    const int FLUSH_INTERVAL = 500;  // More frequent flushing for better memory management
    
    std::cerr << "Processing frames..." << std::endl;
    
    for (size_t i = 0; i < frames.size(); ++i) {
        const FrameInfo& frame = frames[i];
        
        // Progress indicator every 1000 frames
        if ((i + 1) % 1000 == 0 || i == frames.size() - 1) {
            int progress = ((i + 1) * 100) / totalFrames;
            std::cerr << "\rProgress: " << progress << "% (" << (i + 1) << "/" << totalFrames 
                     << ") MS1:" << ms1Count << " MS2:" << ms2Count << "     ";
            std::cerr.flush();
        }
        
        if (frame.msMsType != 0) {
            // Process MS/MS frame
            auto pasefIt = pasefData.find(frame.id);
            if (pasefIt != pasefData.end()) {
                auto scans = data.readScans(frame.id, 0, frame.numScans);
                
                for (const PasefInfo& pasef : pasefIt->second) {
                    auto precIt = precursors.find(pasef.precursorId);
                    if (precIt == precursors.end()) continue;
                    
                    const PrecursorInfo& prec = precIt->second;
                    
                    // Skip precursors with invalid m/z values (NULL/zero from database)
                    if (prec.mz <= 0.0) {
                        skippedPrecursors++;
                        continue;
                    }
                    
                    // Clear and reuse peaks vector
                    peaks.clear();
                    
                    // Process scan range more efficiently
                    int scanStart = std::max(pasef.scanBegin, 0);
                    int scanEnd = std::min(pasef.scanEnd, static_cast<int>(scans.getNbrScans()) - 1);
                    
                    for (int scan = scanStart; scan <= scanEnd; ++scan) {
                        auto nbrPeaks = scans.getNbrPeaks(scan);
                        if (nbrPeaks == 0) continue;
                        
                        auto xAxis = scans.getScanX(scan);
                        auto yAxis = scans.getScanY(scan);
                        
                        // Batch convert indices to masses more efficiently
                        indices.assign(xAxis.first, xAxis.second);
                        if (indices.size() > xAxisMasses.size()) {
                            xAxisMasses.resize(indices.size());
                        }
                        data.indexToMz(frame.id, indices, xAxisMasses);
                        
                        // Collect peaks filtering only zero intensity
                        for (size_t k = 0; k < nbrPeaks; ++k) {
                            if (yAxis.first[k] > 0.0) { // Filter only zero intensity peaks
                                peaks.emplace_back(xAxisMasses[k], yAxis.first[k]);
                            }
                        }
                    }
                    
                    if (!peaks.empty()) { // Process all spectra with any peaks
                        // Calculate mobility using reusable vector
                        unsigned midScan = (scanStart + scanEnd) / 2;
                        scanVec[0] = static_cast<double>(midScan);
                        data.scanNumToOneOverK0(frame.id, scanVec, mobilityVec);
                        
                        // Build MGF entry in string buffer for batch output
                        mgfBuffer_str << "BEGIN IONS\nTITLE=Frame_" << frame.id << "_Precursor_" << pasef.precursorId 
                                     << "_Scans_" << scanStart << "-" << scanEnd 
                                     << "\nRTINSECONDS=" << std::fixed << std::setprecision(6) << frame.time
                                     << "\nMOBILITY=" << mobilityVec[0];
                        
                        if (prec.charge > 0) {
                            mgfBuffer_str << "\nCHARGE=" << prec.charge << "+";
                        }
                        
                        mgfBuffer_str << "\nPEPMASS=" << std::setprecision(6) << prec.mz;
                        if (prec.intensity > 0) {
                            // Output intensity as integer if it's a whole number, otherwise as float
                            if (prec.intensity == static_cast<int>(prec.intensity)) {
                                mgfBuffer_str << " " << static_cast<int>(prec.intensity);
                            } else {
                                mgfBuffer_str << " " << std::setprecision(1) << prec.intensity;
                            }
                        }
                        
                        if (pasef.collisionEnergy > 0) {
                            mgfBuffer_str << "\nCOLLISION_ENERGY=" << pasef.collisionEnergy;
                        }
                        
                        mgfBuffer_str << "\n";
                        
                        // Keep all peaks - no artificial limits for maximum data retention
                        for (const auto& peak : peaks) {
                            mgfBuffer_str << std::setprecision(6) << peak.first << " ";
                            
                            // Output intensity as integer if it's a whole number, otherwise as float
                            if (peak.second == static_cast<int>(peak.second)) {
                                mgfBuffer_str << static_cast<int>(peak.second) << "\n";
                            } else {
                                mgfBuffer_str << std::setprecision(1) << peak.second << "\n";
                            }
                        }
                        
                        mgfBuffer_str << "END IONS\n\n";
                    }
                }
                ms2Count++;
            }
        } else if (ms1File) {
            // Process MS1 frame only if MS1 extraction is enabled
            auto scans = data.readScans(frame.id, 0, frame.numScans);
            
            for (unsigned scan = 0; scan < scans.getNbrScans(); scan += 10) {
                auto nbrPeaks = scans.getNbrPeaks(scan);
                if (nbrPeaks == 0) continue;
                
                auto xAxis = scans.getScanX(scan);
                auto yAxis = scans.getScanY(scan);
                
                // Batch process peaks more efficiently
                indices.assign(xAxis.first, xAxis.second);
                if (indices.size() > xAxisMasses.size()) {
                    xAxisMasses.resize(indices.size());
                }
                data.indexToMz(frame.id, indices, xAxisMasses);
                
                scanVec[0] = static_cast<double>(scan);
                data.scanNumToOneOverK0(frame.id, scanVec, mobilityVec);
                
                // Filter only zero intensity peaks for MS1
                for (size_t k = 0; k < nbrPeaks; ++k) {
                    if (yAxis.first[k] > 0.0) { // Filter only zero intensity peaks
                        ms1Buffer_str << frame.id << "\t" << std::fixed << std::setprecision(6) << frame.time << "\t"
                                     << scan << "\t" << xAxisMasses[k] << "\t";
                        
                        // Output intensity as integer if it's a whole number, otherwise as float
                        if (yAxis.first[k] == static_cast<int>(yAxis.first[k])) {
                            ms1Buffer_str << static_cast<int>(yAxis.first[k]) << "\t";
                        } else {
                            ms1Buffer_str << std::setprecision(1) << yAxis.first[k] << "\t";
                        }
                        
                        ms1Buffer_str << std::setprecision(6) << mobilityVec[0] << "\n";
                    }
                }
            }
            ms1Count++;
        }
        
        // Flush buffers periodically to avoid memory buildup
        if ((i + 1) % FLUSH_INTERVAL == 0) {
            if (!mgfBuffer_str.str().empty()) {
                mgfFile << mgfBuffer_str.str();
                mgfBuffer_str.str("");
                mgfBuffer_str.clear();
            }
            if (ms1File && !ms1Buffer_str.str().empty()) {
                *ms1File << ms1Buffer_str.str();
                ms1Buffer_str.str("");
                ms1Buffer_str.clear();
            }
        }
    }
    
    // Final flush of remaining buffers
    if (!mgfBuffer_str.str().empty()) {
        mgfFile << mgfBuffer_str.str();
    }
    if (ms1File && !ms1Buffer_str.str().empty()) {
        *ms1File << ms1Buffer_str.str();
    }
    
    std::cerr << std::endl;
    std::cout << "Total frames processed: " << totalFrames << std::endl;
    std::cout << "MS1 frames: " << ms1Count << std::endl;
    std::cout << "MS/MS frames: " << ms2Count << std::endl;
    if (skippedPrecursors > 0) {
        std::cout << "Skipped precursors with invalid m/z: " << skippedPrecursors << std::endl;
    }
}

