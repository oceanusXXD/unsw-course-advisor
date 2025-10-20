// src/components/ResizeHandle/ResizeHandle.tsx
import React from "react";

interface ResizeHandleProps {
    onMouseDown: (event: React.MouseEvent<HTMLDivElement>) => void;
}

const ResizeHandle: React.FC<ResizeHandleProps> = ({ onMouseDown }) => {
    return (
        <div
            className="w-full h-full cursor-col-resize"
            onMouseDown={onMouseDown}
            title="Drag to resize"
        >
        </div>
    );
};

export default ResizeHandle;