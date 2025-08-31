import React from 'react';
import Card from './Card';
import Button from './Button';

export default function Modal({ title, children, onClose }) {
  return (
    <div className="fixed inset-0 bg-overlay flex items-center justify-center" onClick={onClose}>
      <Card className="max-w-md w-full" onClick={(e) => e.stopPropagation()}>
        <div className="flex justify-between items-center mb-3">
          <h2 className="text-lg font-medium">{title}</h2>
          <Button variant="ghost" size="sm" onClick={onClose}>
            ×
          </Button>
        </div>
        {children}
      </Card>
    </div>
  );
}
