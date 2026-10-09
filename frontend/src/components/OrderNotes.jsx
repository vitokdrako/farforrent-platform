import React, { useState, useEffect } from 'react';
import { MessageSquare, Trash2, Send } from 'lucide-react';
import axios from 'axios';

const API_URL = process.env.REACT_APP_API_URL;

const OrderNotes = ({ orderId }) => {
  const [notes, setNotes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [newNote, setNewNote] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (orderId) {
      fetchNotes();
    }
  }, [orderId]);

  const fetchNotes = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${API_URL}/api/user-tracking/orders/${orderId}/notes`);
      setNotes(response.data.notes || []);
    } catch (err) {
      console.error('Error fetching notes:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleAddNote = async () => {
    if (!newNote.trim()) return;

    try {
      setSubmitting(true);
      await axios.post(
        `${API_URL}/api/user-tracking/orders/${orderId}/notes`,
        { note: newNote },
        {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`,
            'Content-Type': 'application/json'
          }
        }
      );
      
      setNewNote('');
      await fetchNotes();
    } catch (err) {
      console.error('Error adding note:', err);
      alert('Не вдалося додати нотатку');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteNote = async (noteId) => {
    if (!window.confirm('Видалити цю нотатку?')) return;

    try {
      await axios.delete(
        `${API_URL}/api/user-tracking/notes/${noteId}`,
        {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`
          }
        }
      );
      await fetchNotes();
    } catch (err) {
      console.error('Error deleting note:', err);
      alert('Не вдалося видалити нотатку');
    }
  };

  const formatDate = (timestamp) => {
    if (!timestamp) return '';
    const date = new Date(timestamp);
    return date.toLocaleString('uk-UA', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center p-4">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-corp-primary"></div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-corp-text-dark flex items-center gap-2">
        <MessageSquare className="w-5 h-5 text-corp-primary" />
        Внутрішні нотатки ({notes.length})
      </h3>

      {/* Add note form */}
      <div className="bg-corp-bg-light rounded-corp p-4 border border-corp-border">
        <textarea
          value={newNote}
          onChange={(e) => setNewNote(e.target.value)}
          placeholder="Додати внутрішню нотатку (не видима клієнту)..."
          className="corp-input resize-none"
          rows="3"
        />
        <div className="flex justify-end mt-3">
          <button
            onClick={handleAddNote}
            disabled={!newNote.trim() || submitting}
            className="corp-btn corp-btn-primary flex items-center gap-2 disabled:opacity-50"
          >
            <Send className="w-4 h-4" />
            {submitting ? 'Додаємо...' : 'Додати нотатку'}
          </button>
        </div>
      </div>

      {/* Notes list */}
      {notes.length === 0 ? (
        <div className="corp-empty">
          <MessageSquare className="corp-empty-icon mx-auto" />
          <p className="corp-empty-text">Нотатки відсутні</p>
        </div>
      ) : (
        <div className="space-y-3">
          {notes.map((note) => (
            <div key={note.id} className="corp-card-flat">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1">
                  <p className="text-corp-text-dark whitespace-pre-wrap">{note.note}</p>
                  <div className="flex items-center gap-3 mt-2 text-sm text-corp-text-muted">
                    <span className="font-medium text-corp-primary">{note.created_by_name}</span>
                    <span>•</span>
                    <span>{formatDate(note.created_at)}</span>
                  </div>
                </div>
                <button
                  onClick={() => handleDeleteNote(note.id)}
                  className="text-corp-text-muted hover:text-corp-error transition-colors"
                  title="Видалити нотатку"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default OrderNotes;