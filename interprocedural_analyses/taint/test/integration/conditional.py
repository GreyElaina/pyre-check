def no_precondition_for_if(x):
    if x:
        True
    else:
        False


def no_precondition_for_condition(x):
    return 0 if x else 1


def some_source(name):
    pass


def issue1():
    x = some_source("my-data")
    if x:
        return


def issue2():
    x = some_source("other")
    return 0 if x else 1
