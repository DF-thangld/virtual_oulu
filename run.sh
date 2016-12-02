DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
echo $DIR

source $DIR/bin/activate
python $DIR/main.py
