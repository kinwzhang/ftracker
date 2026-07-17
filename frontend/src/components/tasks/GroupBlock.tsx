import React from 'react';
import type { GroupBlock as GroupBlockType, Group } from '../../types';
import TaskRow from './TaskRow';

interface GroupBlockProps {
  block: GroupBlockType;
  groups: Group[];
  expanded: boolean;
  onToggleExpand: () => void;
  editingTaskId: number | null;
  onEditTask: (id: number) => void;
  onSaveTask: (id: number, data: Record<string, unknown>) => void;
  onDeleteTask: (id: number) => void;
  onToggleTask: (id: number) => void;
  onCommentSave: (id: number, comments: string) => void;
}

const GroupBlockComponent: React.FC<GroupBlockProps> = ({
  block,
  groups,
  expanded,
  onToggleExpand,
  editingTaskId,
  onEditTask,
  onSaveTask,
  onDeleteTask,
  onToggleTask,
  onCommentSave,
}) => {
  const statusClass = `status-${block.summary.status}`;

  return (
    <>
      <tr
        className={`group-summary-row ${statusClass}`}
        onClick={onToggleExpand}
        style={{ cursor: 'pointer' }}
      >
        <td colSpan={8}>
          <div className="d-flex align-items-center justify-content-between">
            <div className="group-summary-counts">
              <strong>{block.group?.name || 'Ungrouped'}</strong>
              <span className="gantt-bar-count ms-3">
                {block.summary.overdue > 0 && (
                  <span className="gantt-bar-count-overdue">
                    <strong>{block.summary.overdue}</strong> overdue
                  </span>
                )}
                {block.summary.pending > 0 && (
                  <span className="gantt-bar-count-pending">
                    <strong>{block.summary.pending}</strong> pending
                  </span>
                )}
                {block.summary.completed > 0 && (
                  <span className="gantt-bar-count-completed">
                    <strong>{block.summary.completed}</strong> done
                  </span>
                )}
              </span>
            </div>
            <span className="text-muted" style={{ fontSize: '0.8rem' }}>
              {expanded ? '▾' : '▸'}
            </span>
          </div>
        </td>
      </tr>
      {expanded &&
        block.tasks.map((task) => (
          <TaskRow
            key={task.id}
            task={task}
            groups={groups}
            isEditing={editingTaskId === task.id}
            onEdit={() => onEditTask(task.id)}
            onSave={(data) => onSaveTask(task.id, data)}
            onDelete={() => onDeleteTask(task.id)}
            onToggle={() => onToggleTask(task.id)}
            onCommentSave={(comments) => onCommentSave(task.id, comments)}
          />
        ))}
    </>
  );
};

export default GroupBlockComponent;
