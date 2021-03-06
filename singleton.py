class NifOp:
    """A simple reference holder class but enables classes to be decoupled.
    This module require initialisation to function."""

    def __init__(self):
        pass

    op = None
    props = None
    context = None

    @staticmethod
    def init(operator, context):
        NifOp.op = operator
        NifOp.props = operator.properties
        NifOp.context = context

        # init loggers logging level
        print(operator)


class NifData:

    data = None

    def __init__(self):
        pass

    @staticmethod
    def init(data):
        NifData.data = data