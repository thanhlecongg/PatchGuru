#!/bin/bash

echo "Creating directory for clones"
cd ..
sudo mkdir clones
sudo chown vscode:vscode clones/
cd clones

echo "Cleaning any existing pandas-dev containers"
docker rm -f pandas-dev1
docker rm -f pandas-dev2
docker rm -f pandas-dev3

mkdir clone1
cd clone1

echo "Creating first clone of pandas"
git clone https://github.com/pandas-dev/pandas.git
cd pandas
echo "Building dev container for pandas (first clone)"
docker build -t pandas-dev .
docker run -t -d --name pandas-dev1 -v ${PWD}:/home/pandas pandas-dev
docker exec pandas-dev1 python -m pip install -ve . --no-build-isolation --config-settings editable-verbose=true
docker exec pandas-dev1 python -m pip install coverage
echo "Done with first clone"

echo "Creating second clone of pandas"
cd ../..
mkdir clone2
cd clone2
cp -r ../clone1/pandas .
cd pandas
echo "Building dev container for pandas (second clone)"
docker run -t -d --name pandas-dev2 -v ${PWD}:/home/pandas pandas-dev
docker exec pandas-dev2 python -m pip install -ve . --no-build-isolation --config-settings editable-verbose=true
docker exec pandas-dev2 python -m pip install coverage
echo "Done with second clone"

echo "Creating third clone of pandas"
cd ../..
mkdir clone3
cd clone3
cp -r ../clone1/pandas .
cd pandas
echo "Building dev container for pandas (third clone)"
docker run -t -d --name pandas-dev3 -v ${PWD}:/home/pandas pandas-dev
docker exec pandas-dev3 python -m pip install -ve . --no-build-isolation --config-settings editable-verbose=true
docker exec pandas-dev3 python -m pip install coverage
echo "Done with third clone"

cd ../../../PatchGuru
