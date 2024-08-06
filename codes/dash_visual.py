import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime, timedelta
import numpy as np

from main import logs_to_time_interval, custom_log_scale

# load case_id list
case_ids = pd.read_csv("../data/case_list.csv")['case_id'].tolist()

# initialize dash app
app = dash.Dash(__name__)

app.layout = html.Div([
	dcc.Dropdown(
		id='case-id-dropdown',
		options=[{'label': i, 'value': i} for i in case_ids],
		value=case_ids[0],
		searchable=True,
		placeholder="Select a case ID"
	),
	dcc.Checklist(
		id='show-waiting',
		options=[{'label': 'Show Waiting Time', 'value': 'show_waiting'}],
		value=[]
	),
	dcc.Graph(id='event-graph')
])


@app.callback(
	Output('event-graph', 'figure'),
	[Input('case-id-dropdown', 'value'), Input('show-waiting', 'value')]
)
def update_graph(selected_case_id, show_waiting):
	# get time intervals for the selected case_id
	time_intervals, case_start = logs_to_time_interval(selected_case_id)

	# create the figure
	fig = go.Figure()

	case_start = (case_start.to_pydatetime()).replace(tzinfo=None)
	idx = 0
	for event_type, interval_list in time_intervals.items():
		for i, interval in enumerate(interval_list):
			original_duration = interval['duration']
			log_duration = custom_log_scale(interval['duration'].total_seconds())
			start_time = (interval['start_time'].to_pydatetime()).replace(tzinfo=None)
			start_time_epoch = (start_time - case_start).total_seconds()
			log_start_dt = custom_log_scale(start_time_epoch)

			# plot the process duration
			fig.add_trace(go.Bar(
				x=[log_duration],
				y=[f"{event_type} {i}"],
				base=[log_start_dt],
				width=0.3,
				name=event_type,
				marker={'color': 'black'},
				orientation='h',
				hoverinfo='text',
				hovertext=f"{event_type}{i} duration: {original_duration}",
				showlegend=False
			))

			if 'show_waiting' in show_waiting:
				for j in range(len(interval['waiting_start'])):
					original_waiting = interval['waiting_duration'][j]
					log_wait_duration = custom_log_scale(interval['waiting_duration'][j].total_seconds())
					log_wait_duration /= 10  # apply different scale to long waiting time
					wait_start_time = (interval['waiting_start'][j].to_pydatetime()).replace(tzinfo=None)
					wait_start_epoch = (wait_start_time - case_start).total_seconds()
					log_wait_start_dt = custom_log_scale(wait_start_epoch)

					# plot the waiting time on the process bar
					fig.add_trace(go.Bar(
						x=[log_wait_duration],
						y=[f"{event_type} {i}"],
						base=[log_wait_start_dt],
						width=0.3,
						name=f'Waiting till resume...{original_waiting}',
						marker={'color': 'silver'},
						orientation='h',
						hoverinfo='text',
						hovertext=f"waiting time: {original_waiting}",
						showlegend=False
					))

			idx += 1

	fig.update_layout(
		barmode='overlay',
		bargap=0.5,
		title=f'case {selected_case_id} process duration and waiting time visualization',
		xaxis=dict(title='time (log-scaled)'),
		yaxis=dict(title=selected_case_id),
		showlegend=True
	)

	# Custom legend elements using dummy Scatter traces
	fig.add_trace(go.Scatter(
		x=[None], y=[None],
		mode='markers',
		marker=dict(size=10, color='black'),
		legendgroup='Processing Time',
		showlegend=True,
		name='Processing Time'
	))
	fig.add_trace(go.Scatter(
		x=[None], y=[None],
		mode='markers',
		marker=dict(size=10, color='silver'),
		legendgroup='Waiting Time',
		showlegend=True,
		name='Waiting Time'
	))

	return fig


if __name__ == '__main__':
	app.run_server(debug=True)



