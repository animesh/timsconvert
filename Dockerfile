# https://github.com/dockersamples/c-plus-plus-docker/blob/main/Dockerfile
# Use the official Ubuntu image as the base image
FROM ubuntu:latest
# Set the working directory in the container
WORKDIR /app
# Install necessary dependencies
RUN apt-get update && apt-get install -y \
    g++ \
    sqlite3 \
    libsqlite3-dev \
# Copy the source code into the container
COPY timsread.cpp .
RUN git clone https://github.com/animesh/CppSQLite/
RUN wget https://customer-download-bbio.bruker.com/d/eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3NTM4NjY4NzUsImlhdCI6MTc1Mzg2Njg3NSwiZmlsZSI6Ii9CREFML0xTTVMvUmF3RGF0YUFjZXNzTGlicmFyaWVzL3RpbXNkYXRhLTIuMjEuMC40LnppcCJ9.NZJMo325mPnDunO-hZBMaj5XdEiJps0axZVfqyFvpdY -O timsdata-2.21.0.4.zip
RUN unzip timsdata-2.21.0.4.zip
# Compile the C++ code 
RUN g++ -O3 -march=native -ICppSQLite/src -Itimsdata-2.21.0.4/timsdata/include/c -Itimsdata-2.21.0.4/timsdata/examples/timsdataSampleCpp/timsdataSampleCpp -o timsread timsread.cpp -LCppSQLite/src -lCppSQLite3 -Ltimsdata-2.21.0.4/timsdata/linux64 -ltimsdata -lsqlite3
# Command to run the API when the container starts
# CMD ["./ok_api"]
ENTRYPOINT ["LD_LIBRARY_PATH=$PWD/timsdata-2.21.0.4/timsdata/linux64", "/app/timsread"]
