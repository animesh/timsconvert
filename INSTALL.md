# Installation Instructions for timsread

## 1. Download Required SDK and Libraries

- **Bruker timsdata SDK**: [TDF-SDK 2.21 (6 MB)](https://www.bruker.com/protected/en/services/software-downloads/mass-spectrometry/raw-data-access-libraries.html?scrollToFormContent=tdf)
    - Download the file: `timsdata-2.21.0.4.zip` (or latest version)
- **CppSQLite3**: [CppSQLite3 GitHub](https://github.com/neosmart/CppSQLite)
    - Download the source: `CppSQLite-master.zip` (or clone the repo)

## 2. Extract Files

- Extract `timsdata-2.21.0.4.zip` to a directory, e.g., `Z:\Download\timsdata-2.21.0.4`.
- Extract `CppSQLite-master.zip` to a directory, e.g., `Z:\Download\CppSQLite-master`.

## 3. Install System Dependencies (on Debian/Ubuntu/WSL2)

```
sudo apt-get update
sudo apt-get install -y g++ libsqlite3-dev
```

## 4. Set Up Include Paths

You will need the following include directories:
- `CppSQLite-master/src` (contains `CppSQLite3.h` and `CppSQLite3.cpp`)
- `timsdata-2.21.0.4/timsdata/include/c` (contains `timsdata.h`)
- `timsdata-2.21.0.4/timsdata/examples/timsdataSampleCpp/timsdataSampleCpp` (contains `timsdata_cpp.h`)

## 5. Compile

From the project directory, run:

```
g++ -I/mnt/z/Download/CppSQLite-master/src \
    -I/mnt/z/Download/timsdata-2.21.0.4/timsdata/include/c \
    -I/mnt/z/Download/timsdata-2.21.0.4/timsdata/examples/timsdataSampleCpp/timsdataSampleCpp \
    -o timsread timsread.cpp \
    -L/mnt/z/Download/CppSQLite-master/src -lCppSQLite3 \
    -L/mnt/z/Download/timsdata-2.21.0.4/timsdata/linux64 -ltimsdata \
    -lsqlite3
```

- Adjust the `/mnt/z/Download/...` paths if your files are located elsewhere.
- On Windows, use the appropriate path format and a compatible compiler (e.g., MSVC).

## 6. Run

The program expects the path to a `.d` directory (not a file) as its argument. It will look for `analysis.tdf` inside the specified directory.

### Example usage:

#### Data [https://www.ebi.ac.uk/pride/archive/projects/PXD057888](https://www.ebi.ac.uk/pride/archive/projects/PXD057888) 

```
wget https://ftp.pride.ebi.ac.uk/pride/data/archive/2024/12/PXD057888/230414_Mathilde_3_Slot2-48_1_4330.d.tar
tar xvf 230414_Mathilde_3_Slot2-48_1_4330.d.tar
```

**On Linux/WSL2:**
```
LD_LIBRARY_PATH=/mnt/z/Download/timsdata-2.21.0.4/timsdata/linux64 ./timsread TIMSTOF/LARS/2023/230414\ mathilde/230414_Mathilde_3_Slot2-48_1_4330.d
```

> **Note:** If you see an error about `libtimsdata.so` not being found, you must set the `LD_LIBRARY_PATH` environment variable to the directory containing `libtimsdata.so` as shown above. This only affects the current run and does not change your system settings.


Pass any required arguments as needed.

---

## Notes
- Ensure all required header and source files are present in the specified directories.
- If you encounter missing dependencies, verify the include paths and that all SDK/library files are extracted.


