import pandas as pd
from datetime import datetime
from datetime import timedelta
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import numpy as np

from pm4py.objects.conversion.log import converter as log_converter
from pm4py.objects.log.util import dataframe_utils
from pm4py.objects.log.util import interval_lifecycle
from pm4py.util import constants
import pm4py


def custom_log_scale(x):
	return np.log10(x + 1)


def plot_time_intervals(all_start, time_interval, id):
	fig, ax = plt.subplots(figsize=(30, 15))

	idx = 0
	all_start = (all_start.to_pydatetime()).replace(tzinfo=None)
	for event_type, interval_list in time_interval.items():
		for interval in interval_list:

			log_duration = custom_log_scale(interval['duration'].total_seconds())
			start_time = (interval['start_time'].to_pydatetime()).replace(tzinfo=None)
			start_time_epoch = (start_time - all_start).total_seconds()
			log_start_dt = custom_log_scale(start_time_epoch)

			# plot the process durations as interval bar in color black
			ax.barh(idx, log_duration, left=log_start_dt,
					height=0.2, align='center', label=event_type, color='black')
			# add text below the bar
			ax.text(log_start_dt, idx + 0.2,
					f"{event_type}", ha='center', va='center', fontsize=6, color='black')

			# plot the waiting time in light gray
			for i in range(len(interval['waiting_start'])):

				log_wait_duration = custom_log_scale(interval['waiting_duration'][i].total_seconds())
				log_wait_duration /= 10
				wait_start_time = (interval['waiting_start'][i].to_pydatetime()).replace(tzinfo=None)
				wait_start_epoch = (wait_start_time - all_start).total_seconds()
				log_wait_start_dt = custom_log_scale(wait_start_epoch)

				ax.barh(idx, log_wait_duration, left=log_wait_start_dt,
						height=0.2, align='center', label='waiting', color='silver')

			idx += 1

	# set y-axis with case_id
	ax.set_label(id)

	# Add a legend for processing time and waiting time
	legend_elements = [
		Patch(facecolor='black', edgecolor='black', label='Processing Time'),
		Patch(facecolor='silver', edgecolor='silver', label='Waiting Time')
	]
	ax.legend(handles=legend_elements, loc='right')

	plt.show()


def read_case_logs(id, path_to_file="../data/BPI Challenge 2017.csv"):
	df_original = pd.read_csv(path_to_file)
	df_id = df_original.loc[df_original['case:concept:name'] == id]
	df_id['time:timestamp'] = pd.to_datetime(df_id['time:timestamp'])
	return df_id


# Function to split the DataFrame into event processes
def split_process(df):
	# Initialize variables
	process_id = 0
	split_dfs = []
	current_process = []

	end_transitions = ['complete', 'withdraw', 'ate_abort']
	# Iterate through the DataFrame
	for index, row in df.iterrows():
		current_process.append(row)
		if row['lifecycle:transition'] in end_transitions:
			# Append current process to the list of split DataFrames
			process_df = pd.DataFrame(current_process)
			process_df['process_id'] = process_id
			split_dfs.append(process_df)
			current_process = []
			process_id += 1

	# Append any remaining events to the last process if any
	if current_process:
		process_df = pd.DataFrame(current_process)
		process_df['process_id'] = process_id
		split_dfs.append(process_df)

	# split process may contain no duration object, drop them when applied
	split_dfs = [process_df for process_df in split_dfs if len(process_df) > 1]

	return split_dfs


# Function to remove duplicate timestamp of schedule and start
def merge_schedule_start(df):
	if 'schedule' in df['lifecycle:transition'].values and 'start' in df['lifecycle:transition'].values:
		# If both schedule and start are present, treat as one timestamp
		return df.iloc[1:]
	else:
		# If only one of schedule or start is present, keep that row
		return df


# Function to preprocess event logs
def log_preprocessing(grouped_logs):
	# step1: remove event process without duration
	grouped_logs = {k: v for k, v in grouped_logs.items() if len(v) > 1}

	# step2: split the logs into separate and complete sub-process for each event_process_type
	split_results = {}
	for event_type, df in grouped_logs.items():
		split_results[event_type] = split_process(df)

	# step3: remove duplicates, we deal with 'schedule' and 'start' as one event, drop 'schedule'
	for event_type, list_dfs in split_results.items():
		for i in range(len(list_dfs)):
			split_results[event_type][i] = merge_schedule_start(split_results[event_type][i])

	return split_results


# Function to mark suspend and resume timestamps as waiting_start and waiting_end
def mark_suspend_resume(df):
	process_end_time = df['time:timestamp'].max()
	suspend_indices = df[df['lifecycle:transition'] == 'suspend'].index
	resume_indices = df[df['lifecycle:transition'] == 'resume'].index

	waiting_start = []
	waiting_time = []

	for suspend_idx in suspend_indices:
		# Find the closest resume timestamp after the suspend timestamp
		closest_resume_idx = resume_indices[(resume_indices > suspend_idx)].min()

		if closest_resume_idx is not np.nan:
			waiting_start.append(df.loc[suspend_idx, 'time:timestamp'])
			waiting_time.append(df.loc[closest_resume_idx, 'time:timestamp'] - df.loc[suspend_idx, 'time:timestamp'])
		else:
			waiting_start.append(df.loc[suspend_idx, 'time:timestamp'])
			waiting_time.append(process_end_time - df.loc[suspend_idx, 'time:timestamp'])  # No resume found

	return waiting_start, waiting_time


def duration_and_waiting_time(p_logs):
	all_time_intervals = {}
	for event_type, list_dfs in p_logs.items():
		if len(list_dfs) > 0:  # exclude process without duration
			event_intervals = []
			for df in list_dfs:
				df_interval = {}
				# compute if there is waiting time interval between suspend and resume
				wait_start, wait_duration = mark_suspend_resume(df)
				df_interval['start_time'] = df['time:timestamp'].min()
				df_interval['duration'] = df['time:timestamp'].max() - df['time:timestamp'].min()
				df_interval['waiting_start'] = wait_start
				df_interval['waiting_duration'] = wait_duration

				event_intervals.append(df_interval)

			all_time_intervals[event_type] = event_intervals

	return all_time_intervals


def logs_to_time_interval(id):
	event_logs = read_case_logs(id)
	case_start_time = event_logs['time:timestamp'].min()
	grouped = event_logs.groupby('concept:name')
	grouped_event_logs = {event_type: group for event_type, group in grouped}

	# process the grouped logs
	processed_logs = log_preprocessing(grouped_event_logs)

	# calculate process duration and waiting time intervals
	time_interval = duration_and_waiting_time(processed_logs)
	return time_interval, case_start_time


if __name__ == "__main__":
	# load event logs of specified case_id and group the logs according to event type
	case_id = 'Application_652823628'
	time_intervals, case_start = logs_to_time_interval(id=case_id)
	plot_time_intervals(case_start, time_interval=time_intervals, id=case_id)
