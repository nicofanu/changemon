# changemon.py #

Changemon is a little tool I wrote to quickly check differences between copies of folders that may have changed. It can also monitor a folder and list files as they are added, changed and removed.

Examples:

    $ changemon.py -c ./a ./b --flags "ar"
    Added
    -----
    
    Removed
    -------
    s

The files that have been added and removed in folder b.

    $ changemon.py -c ./a ./b
    Added
    -----
    
    Changed
    -------
    greet
    t
    z
    
    Removed
    -------
    s

The typical summary.

    $ changemon.py -c ./a ./b --flags "u"
    Unchanged
    ---------
    zerobyte.txt
    nochange.txt

The files that haven't changed in either folder.
