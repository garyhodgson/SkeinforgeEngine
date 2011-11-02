
def _pickle_method(method):
    func_name = method.im_func.__name__
    obj = method.im_self
    cls = method.im_class
    return _unpickle_method, (func_name, obj, cls)

def _unpickle_method(func_name, obj, cls):
   try:
       for cls in cls.mro():
           try:
               func = cls.__dict__[func_name]
           except KeyError:
               pass
           else:
               break
   except AttributeError:
       func = cls.__dict__[func_name]
   return func.__get__(obj, cls)

