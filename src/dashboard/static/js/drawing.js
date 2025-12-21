/**
 * ACMaker Dashboard - Drawing Tools
 * Professional trading chart drawing tools implementation
 */

class DrawingTools {
    constructor(canvasId, chartContainerId) {
        this.canvas = document.getElementById(canvasId);
        this.ctx = this.canvas.getContext('2d');
        this.chartContainer = document.getElementById(chartContainerId);

        this.currentTool = 'cursor';
        this.isDrawing = false;
        this.startX = 0;
        this.startY = 0;
        this.drawings = [];

        this.init();
    }

    init() {
        this.resizeCanvas();
        new ResizeObserver(() => this.resizeCanvas()).observe(this.chartContainer);

        this.canvas.addEventListener('mousedown', (e) => this.onMouseDown(e));
        this.canvas.addEventListener('mousemove', (e) => this.onMouseMove(e));
        this.canvas.addEventListener('mouseup', (e) => this.onMouseUp(e));
        this.canvas.addEventListener('mouseleave', () => this.onMouseLeave());

        document.addEventListener('keydown', (e) => this.onKeyDown(e));

        this.setTool('cursor');
    }

    resizeCanvas() {
        this.canvas.width = this.chartContainer.clientWidth;
        this.canvas.height = this.chartContainer.clientHeight;
        this.redrawAll();
    }

    setTool(tool) {
        this.currentTool = tool;

        // Update UI
        document.querySelectorAll('.draw-btn').forEach(b => b.classList.remove('active'));
        const btnId = 'btn' + tool.charAt(0).toUpperCase() + tool.slice(1);
        const btn = document.getElementById(btnId);
        if (btn) btn.classList.add('active');

        // Toggle canvas interaction
        if (tool !== 'cursor') {
            this.canvas.classList.add('drawing');
        } else {
            this.canvas.classList.remove('drawing');
        }
    }

    clearDrawings() {
        this.drawings = [];
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    }

    redrawAll() {
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

        this.drawings.forEach(d => {
            this.ctx.strokeStyle = d.color || '#00aaff';
            this.ctx.lineWidth = 2;
            this.ctx.setLineDash(d.dashed ? [5, 3] : []);
            this.ctx.beginPath();

            switch (d.type) {
                case 'line':
                    this.ctx.moveTo(d.x1, d.y1);
                    this.ctx.lineTo(d.x2, d.y2);
                    break;

                case 'ray':
                    this.ctx.moveTo(d.x1, d.y1);
                    const dx = d.x2 - d.x1, dy = d.y2 - d.y1;
                    const len = Math.sqrt(dx * dx + dy * dy);
                    const extX = d.x1 + (dx / len) * 2000;
                    const extY = d.y1 + (dy / len) * 2000;
                    this.ctx.lineTo(extX, extY);
                    break;

                case 'hline':
                    this.ctx.moveTo(0, d.y);
                    this.ctx.lineTo(this.canvas.width, d.y);
                    break;

                case 'vline':
                    this.ctx.moveTo(d.x, 0);
                    this.ctx.lineTo(d.x, this.canvas.height);
                    break;

                case 'rect':
                    this.ctx.strokeRect(d.x, d.y, d.w, d.h);
                    this.ctx.setLineDash([]);
                    return;

                case 'fib':
                    this.drawFibonacci(d.y1, d.y2);
                    return;

                case 'cross':
                    this.ctx.moveTo(0, d.y);
                    this.ctx.lineTo(this.canvas.width, d.y);
                    this.ctx.moveTo(d.x, 0);
                    this.ctx.lineTo(d.x, this.canvas.height);
                    break;
            }

            this.ctx.stroke();
            this.ctx.setLineDash([]);
        });
    }

    drawFibonacci(y1, y2) {
        const levels = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1];
        const colors = ['#ff0000', '#ff6600', '#ffaa00', '#00ff00', '#00aaff', '#0066ff', '#ff0000'];
        const dy = y2 - y1;

        levels.forEach((lvl, i) => {
            const y = y1 + dy * lvl;
            this.ctx.strokeStyle = colors[i];
            this.ctx.beginPath();
            this.ctx.moveTo(0, y);
            this.ctx.lineTo(this.canvas.width, y);
            this.ctx.stroke();

            this.ctx.fillStyle = colors[i];
            this.ctx.font = '10px monospace';
            this.ctx.fillText((lvl * 100).toFixed(1) + '%', 5, y - 3);
        });
    }

    getMousePos(e) {
        const rect = this.canvas.getBoundingClientRect();
        return {
            x: e.clientX - rect.left,
            y: e.clientY - rect.top
        };
    }

    onMouseDown(e) {
        if (this.currentTool === 'cursor') return;

        const pos = this.getMousePos(e);
        this.startX = pos.x;
        this.startY = pos.y;

        // Single-click tools
        if (this.currentTool === 'cross') {
            this.drawings.push({ type: 'cross', x: pos.x, y: pos.y, color: '#888888', dashed: true });
            this.redrawAll();
            return;
        }

        if (this.currentTool === 'vline') {
            this.drawings.push({ type: 'vline', x: pos.x, color: '#ff00ff' });
            this.redrawAll();
            return;
        }

        this.isDrawing = true;
    }

    onMouseMove(e) {
        if (!this.isDrawing) return;

        const pos = this.getMousePos(e);

        // Preview
        this.redrawAll();
        this.ctx.strokeStyle = '#00aaff';
        this.ctx.lineWidth = 2;
        this.ctx.setLineDash([]);
        this.ctx.beginPath();

        switch (this.currentTool) {
            case 'line':
                this.ctx.moveTo(this.startX, this.startY);
                this.ctx.lineTo(pos.x, pos.y);
                break;

            case 'ray':
                this.ctx.moveTo(this.startX, this.startY);
                const dx = pos.x - this.startX, dy = pos.y - this.startY;
                const len = Math.sqrt(dx * dx + dy * dy) || 1;
                this.ctx.lineTo(this.startX + (dx / len) * 2000, this.startY + (dy / len) * 2000);
                break;

            case 'hline':
                this.ctx.moveTo(0, this.startY);
                this.ctx.lineTo(this.canvas.width, this.startY);
                break;

            case 'rect':
                this.ctx.strokeRect(this.startX, this.startY, pos.x - this.startX, pos.y - this.startY);
                return;

            case 'fib':
                const levels = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1];
                const dy2 = pos.y - this.startY;
                levels.forEach(lvl => {
                    const ly = this.startY + dy2 * lvl;
                    this.ctx.moveTo(0, ly);
                    this.ctx.lineTo(this.canvas.width, ly);
                });
                break;
        }

        this.ctx.stroke();
    }

    onMouseUp(e) {
        if (!this.isDrawing) return;
        this.isDrawing = false;

        const pos = this.getMousePos(e);

        // Save drawing
        const colors = {
            line: '#00aaff',
            ray: '#00ffff',
            hline: '#ffaa00',
            rect: '#00ff00'
        };

        switch (this.currentTool) {
            case 'line':
                this.drawings.push({ type: 'line', x1: this.startX, y1: this.startY, x2: pos.x, y2: pos.y, color: colors.line });
                break;
            case 'ray':
                this.drawings.push({ type: 'ray', x1: this.startX, y1: this.startY, x2: pos.x, y2: pos.y, color: colors.ray });
                break;
            case 'hline':
                this.drawings.push({ type: 'hline', y: this.startY, color: colors.hline });
                break;
            case 'rect':
                this.drawings.push({ type: 'rect', x: this.startX, y: this.startY, w: pos.x - this.startX, h: pos.y - this.startY, color: colors.rect });
                break;
            case 'fib':
                this.drawings.push({ type: 'fib', y1: this.startY, y2: pos.y });
                break;
        }

        this.redrawAll();
    }

    onMouseLeave() {
        if (this.isDrawing) {
            this.isDrawing = false;
            this.redrawAll();
        }
    }

    onKeyDown(e) {
        const key = e.key.toLowerCase();

        const shortcuts = {
            'v': 'cursor',
            'escape': 'cursor',
            't': 'line',
            'r': 'ray',
            'h': 'hline',
            'f': 'fib',
            'b': 'rect',
            'c': 'cross'
        };

        if (shortcuts[key]) {
            this.setTool(shortcuts[key]);
        } else if (key === 'delete' || key === 'backspace') {
            this.clearDrawings();
        }
    }
}

// Global instance
let drawingTools = null;

function initDrawingTools(canvasId, chartContainerId) {
    drawingTools = new DrawingTools(canvasId, chartContainerId);
    return drawingTools;
}

function setDrawTool(tool) {
    if (drawingTools) {
        drawingTools.setTool(tool);
    }
}

function clearDrawings() {
    if (drawingTools) {
        drawingTools.clearDrawings();
    }
}
