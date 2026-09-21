/**
 * Lightweight toast notification system.
 *
 * Provides success/error/info notifications.
 * No external dependencies — pure DOM manipulation.
 *
 * Usage (in client-side scripts):
 *   import { toast } from '../lib/toast';
 *   toast.success('Research started.');
 *   toast.error('Research failed.');
 *   toast.info('Backend is available.');
 */

export type ToastType = 'success' | 'error' | 'info';

interface Toast {
  id: string;
  type: ToastType;
  message: string;
}

const TOAST_DURATION = 5000; // 5 seconds
const toasts: Toast[] = [];
let containerEl: HTMLDivElement | null = null;

/**
 * Create the toast container if it doesn't exist.
 */
function getContainer(): HTMLDivElement {
  if (containerEl) return containerEl;

  containerEl = document.createElement('div');
  containerEl.setAttribute('aria-live', 'polite');
  containerEl.setAttribute('aria-label', 'Notifications');
  containerEl.className = 'fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm';
  document.body.appendChild(containerEl);
  return containerEl;
}

/**
 * Get icon SVG for toast type.
 */
function getIcon(type: ToastType): string {
  switch (type) {
    case 'success':
      return '<svg class="h-4 w-4 flex-shrink-0 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path d="M5 13l4 4L19 7"/></svg>';
    case 'error':
      return '<svg class="h-4 w-4 flex-shrink-0 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path d="M12 9v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>';
    case 'info':
      return '<svg class="h-4 w-4 flex-shrink-0 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>';
  }
}

/**
 * Get styles for toast type.
 */
function getStyles(type: ToastType): string {
  switch (type) {
    case 'success':
      return 'border-green-200 bg-success-soft text-green-800';
    case 'error':
      return 'border-red-200 bg-red-50 text-red-800';
    case 'info':
      return 'border-blue-200 bg-link-soft text-blue-800';
  }
}

/**
 * Remove a toast by ID.
 */
function removeToast(id: string): void {
  const el = document.getElementById(`toast-${id}`);
  if (el) {
    el.style.opacity = '0';
    el.style.transform = 'translateX(100%)';
    el.style.transition = 'opacity 0.2s, transform 0.2s';
    setTimeout(() => el.remove(), 200);
  }
  const idx = toasts.findIndex((t) => t.id === id);
  if (idx > -1) toasts.splice(idx, 1);
}

/**
 * Show a toast notification.
 */
function showToast(type: ToastType, message: string): void {
  const id = `toast-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
  const container = getContainer();

  const el = document.createElement('div');
  el.id = `toast-${id}`;
  el.setAttribute('role', 'status');
  el.className = `flex items-start gap-3 rounded-md border px-4 py-3 text-sm shadow-lg transition-all ${getStyles(type)}`;
  el.style.opacity = '0';
  el.style.transform = 'translateX(100%)';
  el.innerHTML = `
    ${getIcon(type)}
    <span class="flex-1">${escapeHtml(message)}</span>
    <button class="flex-shrink-0 text-current opacity-60 hover:opacity-100" aria-label="Dismiss" onclick="this.closest('[id^=toast-]').remove()">
      <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
        <path d="M6 18L18 6M6 6l12 12"/>
      </svg>
    </button>
  `;

  container.appendChild(el);

  // Animate in
  requestAnimationFrame(() => {
    el.style.opacity = '1';
    el.style.transform = 'translateX(0)';
    el.style.transition = 'opacity 0.2s, transform 0.2s';
  });

  // Auto-dismiss
  setTimeout(() => removeToast(id), TOAST_DURATION);
}

function escapeHtml(str: string): string {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

/**
 * Toast API.
 */
export const toast = {
  success: (message: string) => showToast('success', message),
  error: (message: string) => showToast('error', message),
  info: (message: string) => showToast('info', message),
};
