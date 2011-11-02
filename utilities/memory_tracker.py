'''
Wrapper of pympler tracker for memory profiling.
'''

from pympler.classtracker import ClassTracker

tracker = ClassTracker()

def track_object(o):
    tracker.track_object(o, resolution_level=2)
    
def track_class(c):
    tracker.track_class(c, trace=1, resolution_level=1)

def create_snapshot(tag):
    tracker.create_snapshot(tag)