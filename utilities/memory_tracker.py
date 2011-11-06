'''
Wrapper of pympler tracker for memory profiling.
'''

try:
    #Exception checked as pypy complains
    from pympler.classtracker import ClassTracker
    tracker = ClassTracker()
except:
    tracker = None


def track_object(o):
    if tracker != None:
        tracker.track_object(o, resolution_level=2)
    
def track_class(c):
    if tracker != None:
        tracker.track_class(c, trace=1, resolution_level=1)

def create_snapshot(tag):
    if tracker != None:
        tracker.create_snapshot(tag)