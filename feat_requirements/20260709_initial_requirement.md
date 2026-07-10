Working protocol: follow 1. analysis, put down plan, 2. design, 3. implementation, 4. testing, 5. documentation

This is a tracker application to keep track of monthly tasks for the team.

Application Name: FRTB Montly Activities Tracker
Main features of the application include::
1. task tracking table with the following columns:
   - Task Name(string)
   - Assigned To (string)
   - SLA (days) (integer)
   - SLA (type:[ "Business Day", "Calendar Day"])
   - Scheduled Date (date)
   - Finished (boolean)
   - Completion Date (date)
   - Comments (string)
2. A gantt chart to visualize the tasks and their timelines
3. A dashboard to show the summary of tasks, including the number of completed tasks, pending tasks, and overdue tasks.
4. A date picker to select the month for which the tasks are being tracked.
5. Should be able to generate a new task list for the next month based on the task template.
6. Should be able to calcuate the scheduled date based on the SLA and the selected month.
7. Should be weekend and HK public holiday aware when calculating the scheduled date based on the SLA.
8. Use a SQLite database to store the task data.
9. Has the ability to export reports in HTML and CSV format to satisfy audittrail, all changes and modify should be recorded.

This application should be built with Django framework.

--- Enhancement Requests ---
E1. put the dashboard statistics into the main page. It doesn't have to be so big, just a simple summary of the number of completed tasks, pending tasks, and overdue tasks.
E2. Add a tab for "Task Template", so that population of new month can reference the template and generate tasks accordingly.
E3. In the task list, when marking finished, popluate Completion date and time automatically.
E4. In the task list, allow marking finished and input comment just in place, offer a check box for finished, and double click on comment field to edit in place, save immediately when losing focus.
E5. On the task list, allow to add new task in place, just for the month.
E6. Offer to check the list of public holidays in HK for the selected month or the year, in a list.
E7. For audit trails, offer the JSON format, but also a line saying {user} has modified {field} from {old_value} to {new_value} at {timestamp} for better readability.
E8. Completed task with a light green background, overdue task with a light red background, and pending task with a light yellow background in the task list for better visual distinction.

--- Bug Fixing and Enhancements ---
B1. When finished adding a comment, the page will jump to a plain page with the comment just input, it should stay on the page.
B2. Item in task list should be colored coded: 
   - Completed task with a light green background
   - Overdue task with a light red background
   - Pending task with a light yellow background
B3. Item should be sorted by scheduled date, with the earliest date on top, however, finished tasks should be behind the pending and overdue tasks, sorted by completion date, with the earliest date on top.
B4. Holiday list should show the name of public holiday, not just the date.
E9. Change the title to "Monthly Activities Tracker", put in document where to update that.
E10. Change the UI into card based layout with glass style element, light background, and dark text, with a modern look and feel.

--- Enhancement Requests ---
E11. Edit button in task list and template list don't need to jump a new page, but instead providng editing box or calendar for selecting date in place, and have a save button. To save changes.
E12. For task list, delete button only appear when in Edit mode, and a confirmation dialog should appear in place for confirmation. For template list, delete button remains visible all the time.
E13. In template view, should be "add task" instead of "add template"
E14. Change Business Day into Working Day, when in edit mode, show full "Working Day" or "Calendar Day", but in view mode shows WD or CD.