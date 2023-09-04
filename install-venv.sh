#!/bin/sh
set -e
venv_folder=$(readlink -f ~/.gle/venv)
python3 -m venv --clear --copies ${venv_folder}
. ${venv_folder}/bin/activate
python3 -m pip install gitlab-emulator
echo "gitlab emulator installed in ${venv_folder}"
echo "you should append ${venv_folder}/bin to PATH or create shell aliases, eg:"
for prog in $(ls ${venv_folder}/bin/gl*)
do
  echo "alias $(basename $prog)=$prog"
done