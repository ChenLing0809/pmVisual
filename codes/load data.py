import pandas
import pm4py

# load the XES event log
log = pm4py.read_xes("../data/BPI Challenge 2017_1_all/BPI Challenge 2017.xes")

# convert event logs to pandas Dataframe
df = pm4py.convert_to_dataframe(log)
num_case = len(df['case:concept:name'].unique())
num_event_origin = len(df['EventOrigin'].unique())
num_activity = len(df['concept:name'].unique())
print(df['concept:name'].unique())
print(num_case)
print(num_event_origin)
print(num_activity)
print('u')