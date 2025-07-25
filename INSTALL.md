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
TDF file TIMSTOF/LARS/2023/230414 mathilde/230414_Mathilde_3_Slot2-48_1_4330.d contains 66565 frames.
Frame 1 has retention time 0.65112501 seconds
Scan 42 --- 1/K0: 1.5713494
x (index)    :    288484 
x (m/z)      : 1072.4621 
y (intensity):        78 

Scan 46 --- 1/K0: 1.5671132
x (index)    :    298252 
x (m/z)      : 1123.5056 
y (intensity):        38 

Scan 47 --- 1/K0: 1.5660539

...
...
...

Frame 66565 has retention time 7199.938 seconds
Scan 90 --- 1/K0: 1.5204062
x (index)    :    166320 
x (m/z)      : 534.30582 
y (intensity):        10 
...
...
...
Scan 813 --- 1/K0: 0.72330414
x (index)    :    304931 
x (m/z)      : 1159.0903 
y (intensity):        10 

```

> **Note:** If you see an error about `libtimsdata.so` not being found, you must set the `LD_LIBRARY_PATH` environment variable to the directory containing `libtimsdata.so` as shown above. This only affects the current run and does not change your system settings.


Pass any required arguments as needed.

---

## Notes
- Ensure all required header and source files are present in the specified directories.
- If you encounter missing dependencies, verify the include paths and that all SDK/library files are extracted.


