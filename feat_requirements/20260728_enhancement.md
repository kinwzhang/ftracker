## Finished late Items
1. add a category: finished late, if an item's marked finished timestamp is later than the set SLA time.
2. finished late items should be marked with another color other than any existing one.
3. finished late items should be easiliy noticed in the gantt chart as well, so that user knows at a glance one or more items in the group finished late, if all items from the group are finished. If the group has items in progress/overdue, honor in progress/overdue.
4. if all items from a group are finished, shows x completed(y ontime, z finished late)

## system rerun tracker
In the task list, for each task, provide a checkbox for user to indicate whether one or more system rerun were triggered for completing the task.
Once user check it, show 3 items for user to input:
 - System: dropdown list
 - Rerun triggered at: date and timestamp
 - Rerun completed at: date and timestamp
users are allowed to log more than one rerun items for a task, so allow a + sign for user to log if more reun happened.

In the Gantt chart, add a group "System rerun"
 - when it is collapsed, show how many rerun happened, then plot all rerun on the day of rerun, if the rerun take more than a day to finish, there should be a bar starting from the day through our the end day.
 - when it is expanded, each system should have its own bar to indicate all reruns for that system.
 - in the dashboard tag, should have an aggregation table to list all rerun entries from the month, labeling which tasks trigger the rerun, as well as rerun statistics

## table of comment
Below the task list, create a table of comments, if at least one user has provided comment for a task.
|Task Name|Comment|

In the task list, allow user to input multi-line comments, press enter for new line. content saved when input box loss focus.
