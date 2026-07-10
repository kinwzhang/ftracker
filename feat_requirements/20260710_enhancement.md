--- Enhancement and Bugs---
E1. In Tasks and Dashboard tab, near the month selection, add the "previous" and "next" buttons to quickly jump to previous or next month. Also keep the current go button.
E2. Eash task should carry one more attribute: Gruop. Add group by feature in the task list. When Collasped, the Gantt Chart can show progress by grouping.
    - Task 1, 2,3 belong to Task Group A
    - Task 4, 5 belong to Task Group B
    - Task 6, 7, 8 belong to Task Group C
    Gannt Chart can show Group A, Group B, and Group C, user is allow to expand on particular group to see progress of individual tasks. Same behavior for the task list.
    - Add a button to expand all and collaspe all groups in the task list and Gantt chart.
E2.1. Gantt chart logic for group, 
    - When a group is collapsed, the Gantt chart should show the earliest start date and latest end date of all tasks in that group as a single bar.
        - if a task within a group is overdue, the whole group is overdue.
        - only if all tasks within a group are completed, the whole group is completed.
        - the bar of group should be lenght of the next cloest due date of the tasks within that group, and the color of the bar should be based on the status of the group (completed, pending, overdue).
    - When a group is expanded, the Gantt chart should show individual bars for each task in that group, with their respective start and end dates.
E3. In templates tabs, add a section for group management, allow user to add, edit, and delete group names.
E4. Sorting order should be validated and not allow duplicate. If 1, 2, 3 are already used, and user is trying to add another task with sort order 2, the new task should become 3, and the original 3 should become 4, etc.
B1. The bars in Gantt chart is not aligning with the date rule on the top. (The current bar seems not changing width as the window size changes)

--- Enhancement and Bugs Round 2---
B2. Groups are created, and tasks are assigned with groups, but not reflected in the Gantt chart or task lists. 
E4. Allow editing on multiple tasks in task list or template list, by clicking a overall save button instead of clicking save per item.
B3. The task list layout changed after clicking on the "Edit" button, 
 - in "Tasks" tab, when clicking Edit in Task List, it displays "Save" in a line and "Del" in the second line. Better have "Save" and "Del" next to each other.
   - in "Tasks" tab, when clicking "Del", it displays a new line with "No", and "Confirm" button in the same place as where "Del" was, better to have "No" and "Confirm" on the right of "No", and "Save", "No", "Confirm" in the same line.
 - in "template" tab, when clicking Edit in Template List when clicing "Edit", it displays "Save" and "Cancel" in a line, and "Del" in the second line. Better have "Save", "Cancel", and "Del" next to each other.

--- Enhancement and Bugs Round 3---
B4. In the Gantt chart, the bar for group is not showing the correct length:
    - The bar for a group should represent the duration from the earliest start date to the latest end date of all tasks within that group in principle (if all pending or completed, solid color bar)
    - If any tasks within a group are overdue or pending, the bar should honor the bar color (overdue > pending > complete) and show the most overdue bar with solid color, and the rest of the bar should be in lighter color to indicate that there are pending tasks within that group.
    - No need to show the bar for completed tasks within a group, unless all tasks within that group are completed, in which case the bar should be solid color to indicate completion.
B5. Carlibrate the holiday calendar with below:
General holidays for 2027
The first day of January	1 January	Friday
Lunar New Year’s Day	6 February	Saturday
The third day of Lunar New Year	8 February	Monday
The fourth day of Lunar New Year	9 February	Tuesday
Good Friday	26 March	Friday
The day following Good Friday	27 March	Saturday
Easter Monday	29 March	Monday
Ching Ming Festival	5 April	Monday
Labour Day	1 May	Saturday
The Birthday of the Buddha	13 May	Thursday
Tuen Ng Festival	9 June	Wednesday
Hong Kong Special Administrative Region Establishment Day	1 July	Thursday
The day following the Chinese Mid-Autumn Festival	16 September	Thursday
National Day	1 October	Friday
Chung Yeung Festival	8 October	Friday
Christmas Day	25 December	Saturday
The first weekday after Christmas Day	27 December	Monday

General holidays for 2026
The first day of January	1 January	Thursday
Lunar New Year’s Day	17 February	Tuesday
The second day of Lunar New Year	18 February	Wednesday
The third day of Lunar New Year	19 February	Thursday
Good Friday	3 April	Friday
The day following Good Friday	4 April	Saturday
The day following Ching Ming Festival	6 April	Monday
The day following Easter Monday	7 April	Tuesday
Labour Day	1 May	Friday
The day following the Birthday of the Buddha	25 May	Monday
Tuen Ng Festival	19 June	Friday
Hong Kong Special Administrative Region Establishment Day	1 July	Wednesday
The day following the Chinese Mid-Autumn Festival	26 September	Saturday
National Day	1 October	Thursday
The day following Chung Yeung Festival	19 October	Monday
Christmas Day	25 December	Friday
The first weekday after Christmas Day	26 December	Saturday

--- Enhancement and Bugs Round 4---
E5. In the Gantt chart, make the group bar:
  - color coded(matching color with task list items): if any iteam within the group is overdue, the group bar should be red; if all items are completed, the group bar should be green; if any item is pending, the group bar should be blue. Honor overdur > in progress > completed.
  - display information: "x items overdue[Heavy Red], y items pending[Heavy Blue], z items completed[Heavy Green]" on the group bar.
E6. Add Expand all and Collapse all buttons in the task list
B6. The date bar on the Gantt chart is not aligned with the task bars, it is now aligning with task items in the Gantt chart.

--- Enhancement and Bugs Round 5 ---
B7. The Length of Group Bar should always be the length of the longest task within that group, and the color of the group bar should be based on the status of the group (completed, pending, overdue).
B8. The Gant Chart and Task List is linked together on Expand all or Collaspe all. it is not necessary, just let them maintain their own status.
B9. Whenever marking a task finished, it will expand the whole list. It is not necessary, just maintain Expand status.

B10. The Scheduled date for tasks with Calendar Day is not populating correct, which has skipped the public holiday. Calendar Day pin on the exact day regardless holiday or weekends.