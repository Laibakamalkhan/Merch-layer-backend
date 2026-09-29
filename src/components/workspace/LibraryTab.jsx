import React, { useEffect, useState } from 'react';
import { api } from '../../lib/api';
import { useAuth } from '../../context/AuthContext';
import { 
  Library, Clock, MessageSquare, ArrowRight, Sparkles, 
  Trash2, Copy, Check, ChevronRight, BarChart2 
} from 'lucide-react';


export default function LibraryTab({ onResumeTask }) {
  const { tenantId } = useAuth();
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    api.library(tenantId)
      .then((d) => setTasks(d.items.map((it) => ({
        id: it.id,
        title: it.title || 'Untitled',
        category: it.type,
        store: '',
        model: '',
        date: new Date(it.updated_at || it.created_at).toLocaleString(),
        preview: it.metadata?.preview || it.metadata?.summary || '',
      }))))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [tenantId]);
  const [copiedId, setCopiedId] = useState(null);

  const handleCopy = (id, e) => {
    e.stopPropagation();
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 1500);
  };

  return (
    <div className="workspace-library">
      <div className="workspace-connectors__header">
        <div>
          <h2 className="workspace-connectors__title">Task Library & AI History</h2>
          <p className="workspace-connectors__subtitle">
            Revisit past agent analysis sessions, generated SQL queries, schema mappings, and multi-store reports.
          </p>
        </div>
      </div>

      {error && <p role="alert" style={{ color: '#F87171' }}>⚠ {error}</p>}
      {!loading && !error && tasks.length === 0 && <p style={{ opacity: .7 }}>No saved tasks yet. Ask the AI something and it will appear here.</p>}

      <div className="workspace-library__list">
        {tasks.map((task) => (
          <div 
            key={task.id} 
            className="library-task-card"
            onClick={() => onResumeTask && onResumeTask(task)}
          >
            <div className="library-task-card__top">
              <div className="library-task-card__tags">
                <span className="library-category-tag">{task.category}</span>
                {task.store && <span className="library-store-tag">{task.store}</span>}
                {task.model && <span className="library-model-tag">{task.model}</span>}
              </div>
              <div className="library-task-card__meta">
                <span className="library-date"><Clock size={13} /> {task.date}</span>
              </div>
            </div>

            <h3 className="library-task-card__title">{task.title}</h3>
            <p className="library-task-card__preview">{task.preview}</p>

            <div className="library-task-card__bottom">
              <span className="resume-prompt">
                <Sparkles size={14} /> Resume this task <ChevronRight size={14} />
              </span>

              <button 
                className="library-icon-btn" 
                onClick={(e) => handleCopy(task.id, e)}
                title="Copy prompt"
              >
                {copiedId === task.id ? <Check size={14} style={{ color: '#10B981' }} /> : <Copy size={14} />}
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
