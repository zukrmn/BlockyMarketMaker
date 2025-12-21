/**
 * ACMaker Dashboard - Drawing Tools
 * Professional trading chart drawing tools with selection and context menu
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
        this.selectedIndex = -1;
        this.hoveredIndex = -1;
        this.isDragging = false;
        this.dragOffsetX = 0;
        this.dragOffsetY = 0;

        this.init();
        this.createContextMenu();
    }

    init() {
        this.resizeCanvas();
        new ResizeObserver(() => this.resizeCanvas()).observe(this.chartContainer);

        this.canvas.addEventListener('mousedown', (e) => this.onMouseDown(e));
        this.canvas.addEventListener('mousemove', (e) => this.onMouseMove(e));
        this.canvas.addEventListener('mouseup', (e) => this.onMouseUp(e));
        this.canvas.addEventListener('mouseleave', () => this.onMouseLeave());
        this.canvas.addEventListener('dblclick', (e) => this.onDoubleClick(e));
        this.canvas.addEventListener('contextmenu', (e) => this.onContextMenu(e));

        document.addEventListener('keydown', (e) => this.onKeyDown(e));
        document.addEventListener('click', (e) => this.hideContextMenu(e));

        this.setTool('cursor');
    }

    createContextMenu() {
        // Create context menu element
        this.contextMenu = document.createElement('div');
        this.contextMenu.className = 'drawing-context-menu';
        this.contextMenu.innerHTML = `
            <div class="ctx-item" data-action="edit">
                <span class="ctx-icon">✏️</span> Editar
            </div>
            <div class="ctx-item" data-action="clone">
                <span class="ctx-icon">📋</span> Duplicar
            </div>
            <div class="ctx-separator"></div>
            <div class="ctx-item" data-action="color-blue">
                <span class="ctx-color" style="background:#00aaff"></span> Azul
            </div>
            <div class="ctx-item" data-action="color-green">
                <span class="ctx-color" style="background:#00ff00"></span> Verde
            </div>
            <div class="ctx-item" data-action="color-red">
                <span class="ctx-color" style="background:#ff0000"></span> Vermelho
            </div>
            <div class="ctx-item" data-action="color-yellow">
                <span class="ctx-color" style="background:#ffaa00"></span> Amarelo
            </div>
            <div class="ctx-item" data-action="color-purple">
                <span class="ctx-color" style="background:#ff00ff"></span> Roxo
            </div>
            <div class="ctx-separator"></div>
            <div class="ctx-item ctx-danger" data-action="delete">
                <span class="ctx-icon">🗑️</span> Excluir
            </div>
        `;
        this.contextMenu.style.display = 'none';
        document.body.appendChild(this.contextMenu);

        // Add event listener for menu items
        this.contextMenu.addEventListener('click', (e) => {
            const item = e.target.closest('.ctx-item');
            if (item) {
                this.handleContextAction(item.dataset.action);
            }
        });

        // Add styles
        this.addContextMenuStyles();
        this.createFloatingToolbar();
    }

    createFloatingToolbar() {
        // Create floating toolbar that appears on selection
        this.floatingToolbar = document.createElement('div');
        this.floatingToolbar.className = 'drawing-floating-toolbar';
        this.floatingToolbar.innerHTML = `
            <button class="ftb-btn" data-action="color-blue" title="Azul">
                <span style="background:#00aaff"></span>
            </button>
            <button class="ftb-btn" data-action="color-green" title="Verde">
                <span style="background:#00ff00"></span>
            </button>
            <button class="ftb-btn" data-action="color-red" title="Vermelho">
                <span style="background:#ff0000"></span>
            </button>
            <button class="ftb-btn" data-action="color-yellow" title="Amarelo">
                <span style="background:#ffaa00"></span>
            </button>
            <button class="ftb-btn" data-action="color-purple" title="Roxo">
                <span style="background:#ff00ff"></span>
            </button>
            <div class="ftb-separator"></div>
            <button class="ftb-btn" data-action="clone" title="Duplicar">📋</button>
            <button class="ftb-btn ftb-danger" data-action="delete" title="Excluir">🗑️</button>
        `;
        this.floatingToolbar.style.display = 'none';
        document.body.appendChild(this.floatingToolbar);

        // Add event listener
        this.floatingToolbar.addEventListener('click', (e) => {
            const btn = e.target.closest('.ftb-btn');
            if (btn) {
                this.handleContextAction(btn.dataset.action);
            }
        });
    }

    addContextMenuStyles() {
        if (document.getElementById('ctx-menu-styles')) return;

        const style = document.createElement('style');
        style.id = 'ctx-menu-styles';
        style.textContent = `
            .drawing-context-menu {
                position: fixed;
                background: #1a1a1a;
                border: 1px solid #333;
                border-radius: 6px;
                padding: 4px 0;
                min-width: 150px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.5);
                z-index: 1000;
                font-family: -apple-system, sans-serif;
                font-size: 12px;
            }
            .ctx-item {
                display: flex;
                align-items: center;
                gap: 8px;
                padding: 8px 12px;
                cursor: pointer;
                color: #e0e0e0;
            }
            .ctx-item:hover {
                background: rgba(0,170,255,0.2);
            }
            .ctx-item.ctx-danger:hover {
                background: rgba(255,0,0,0.2);
            }
            .ctx-icon {
                width: 16px;
                text-align: center;
            }
            .ctx-color {
                width: 14px;
                height: 14px;
                border-radius: 3px;
                border: 1px solid #555;
            }
            .ctx-separator {
                height: 1px;
                background: #333;
                margin: 4px 0;
            }
            
            /* Floating Toolbar */
            .drawing-floating-toolbar {
                position: fixed;
                background: #1a1a1a;
                border: 1px solid #444;
                border-radius: 6px;
                padding: 4px 6px;
                display: flex;
                align-items: center;
                gap: 4px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.5);
                z-index: 999;
            }
            .ftb-btn {
                width: 28px;
                height: 28px;
                border: none;
                background: transparent;
                border-radius: 4px;
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 14px;
            }
            .ftb-btn:hover {
                background: rgba(255,255,255,0.1);
            }
            .ftb-btn span {
                width: 16px;
                height: 16px;
                border-radius: 3px;
                border: 1px solid #666;
            }
            .ftb-btn.ftb-danger:hover {
                background: rgba(255,0,0,0.2);
            }
            .ftb-separator {
                width: 1px;
                height: 20px;
                background: #444;
                margin: 0 4px;
            }
        `;
        document.head.appendChild(style);
    }

    showContextMenu(x, y) {
        this.contextMenu.style.left = x + 'px';
        this.contextMenu.style.top = y + 'px';
        this.contextMenu.style.display = 'block';
    }

    hideContextMenu(e) {
        if (!this.contextMenu.contains(e?.target)) {
            this.contextMenu.style.display = 'none';
        }
    }

    handleContextAction(action) {
        if (this.selectedIndex < 0) return;

        const drawing = this.drawings[this.selectedIndex];

        switch (action) {
            case 'delete':
                this.drawings.splice(this.selectedIndex, 1);
                this.selectedIndex = -1;
                break;

            case 'clone':
                const clone = JSON.parse(JSON.stringify(drawing));
                // Offset the clone slightly
                if (clone.x1 !== undefined) { clone.x1 += 20; clone.x2 += 20; }
                if (clone.y1 !== undefined) { clone.y1 += 20; clone.y2 += 20; }
                if (clone.x !== undefined) clone.x += 20;
                if (clone.y !== undefined) clone.y += 20;
                this.drawings.push(clone);
                this.selectedIndex = this.drawings.length - 1;
                break;

            case 'color-blue':
                drawing.color = '#00aaff';
                break;
            case 'color-green':
                drawing.color = '#00ff00';
                break;
            case 'color-red':
                drawing.color = '#ff0000';
                break;
            case 'color-yellow':
                drawing.color = '#ffaa00';
                break;
            case 'color-purple':
                drawing.color = '#ff00ff';
                break;
        }

        this.contextMenu.style.display = 'none';
        this.redrawAll();
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
        // 'cursor' = chart interaction (canvas transparent to events)
        // 'select' = drawing selection/move
        // other = drawing mode
        if (tool === 'cursor') {
            this.canvas.classList.remove('drawing');
            this.canvas.style.pointerEvents = 'none';
            this.selectedIndex = -1;
            this.redrawAll();
        } else {
            this.canvas.classList.add('drawing');
            this.canvas.style.pointerEvents = 'auto';
        }

        // Deselect when switching to drawing tool (not select)
        if (tool !== 'cursor' && tool !== 'select') {
            this.selectedIndex = -1;
            this.redrawAll();
        }
    }

    clearDrawings() {
        this.drawings = [];
        this.selectedIndex = -1;
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    }

    deleteSelected() {
        if (this.selectedIndex >= 0) {
            this.drawings.splice(this.selectedIndex, 1);
            this.selectedIndex = -1;
            this.redrawAll();
        }
    }

    // Hit testing - check if point is near a drawing
    hitTest(x, y) {
        const threshold = 10;

        for (let i = this.drawings.length - 1; i >= 0; i--) {
            const d = this.drawings[i];

            switch (d.type) {
                case 'line':
                case 'ray':
                    if (this.pointToLineDistance(x, y, d.x1, d.y1, d.x2, d.y2) < threshold) {
                        return i;
                    }
                    break;

                case 'hline':
                    if (Math.abs(y - d.y) < threshold) {
                        return i;
                    }
                    break;

                case 'vline':
                    if (Math.abs(x - d.x) < threshold) {
                        return i;
                    }
                    break;

                case 'rect':
                    // Check if near any edge of rectangle
                    const nearTop = Math.abs(y - d.y) < threshold && x >= d.x && x <= d.x + d.w;
                    const nearBottom = Math.abs(y - (d.y + d.h)) < threshold && x >= d.x && x <= d.x + d.w;
                    const nearLeft = Math.abs(x - d.x) < threshold && y >= d.y && y <= d.y + d.h;
                    const nearRight = Math.abs(x - (d.x + d.w)) < threshold && y >= d.y && y <= d.y + d.h;
                    if (nearTop || nearBottom || nearLeft || nearRight) {
                        return i;
                    }
                    break;

                case 'cross':
                    if (Math.abs(x - d.x) < threshold || Math.abs(y - d.y) < threshold) {
                        return i;
                    }
                    break;

                case 'fib':
                    const levels = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1];
                    const dy = d.y2 - d.y1;
                    for (const lvl of levels) {
                        const ly = d.y1 + dy * lvl;
                        if (Math.abs(y - ly) < threshold) {
                            return i;
                        }
                    }
                    break;
            }
        }
        return -1;
    }

    pointToLineDistance(px, py, x1, y1, x2, y2) {
        const A = px - x1;
        const B = py - y1;
        const C = x2 - x1;
        const D = y2 - y1;
        const dot = A * C + B * D;
        const lenSq = C * C + D * D;
        let param = lenSq !== 0 ? dot / lenSq : -1;

        let xx, yy;
        if (param < 0) { xx = x1; yy = y1; }
        else if (param > 1) { xx = x2; yy = y2; }
        else { xx = x1 + param * C; yy = y1 + param * D; }

        return Math.sqrt((px - xx) ** 2 + (py - yy) ** 2);
    }

    redrawAll() {
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

        this.drawings.forEach((d, index) => {
            const isSelected = index === this.selectedIndex;
            const isHovered = index === this.hoveredIndex;

            this.ctx.strokeStyle = d.color || '#00aaff';
            this.ctx.lineWidth = isSelected ? 3 : 2;
            this.ctx.setLineDash(d.dashed ? [5, 3] : []);

            // Selection glow effect
            if (isSelected) {
                this.ctx.shadowColor = d.color || '#00aaff';
                this.ctx.shadowBlur = 8;
            } else if (isHovered) {
                this.ctx.shadowColor = '#ffffff';
                this.ctx.shadowBlur = 4;
            } else {
                this.ctx.shadowBlur = 0;
            }

            this.ctx.beginPath();

            switch (d.type) {
                case 'line':
                    this.ctx.moveTo(d.x1, d.y1);
                    this.ctx.lineTo(d.x2, d.y2);
                    // Draw handles if selected
                    if (isSelected) {
                        this.drawHandle(d.x1, d.y1);
                        this.drawHandle(d.x2, d.y2);
                    }
                    break;

                case 'ray':
                    this.ctx.moveTo(d.x1, d.y1);
                    const dx = d.x2 - d.x1, dy = d.y2 - d.y1;
                    const len = Math.sqrt(dx * dx + dy * dy);
                    const extX = d.x1 + (dx / len) * 2000;
                    const extY = d.y1 + (dy / len) * 2000;
                    this.ctx.lineTo(extX, extY);
                    if (isSelected) {
                        this.drawHandle(d.x1, d.y1);
                    }
                    break;

                case 'hline':
                    this.ctx.moveTo(0, d.y);
                    this.ctx.lineTo(this.canvas.width, d.y);
                    if (isSelected) {
                        this.drawHandle(50, d.y);
                    }
                    break;

                case 'vline':
                    this.ctx.moveTo(d.x, 0);
                    this.ctx.lineTo(d.x, this.canvas.height);
                    if (isSelected) {
                        this.drawHandle(d.x, 50);
                    }
                    break;

                case 'rect':
                    this.ctx.strokeRect(d.x, d.y, d.w, d.h);
                    if (isSelected) {
                        this.drawHandle(d.x, d.y);
                        this.drawHandle(d.x + d.w, d.y);
                        this.drawHandle(d.x, d.y + d.h);
                        this.drawHandle(d.x + d.w, d.y + d.h);
                    }
                    this.ctx.shadowBlur = 0;
                    this.ctx.setLineDash([]);
                    return;

                case 'fib':
                    this.drawFibonacci(d.y1, d.y2, isSelected);
                    this.ctx.shadowBlur = 0;
                    return;

                case 'cross':
                    this.ctx.moveTo(0, d.y);
                    this.ctx.lineTo(this.canvas.width, d.y);
                    this.ctx.moveTo(d.x, 0);
                    this.ctx.lineTo(d.x, this.canvas.height);
                    if (isSelected) {
                        this.drawHandle(d.x, d.y);
                    }
                    break;
            }

            this.ctx.stroke();
            this.ctx.shadowBlur = 0;
            this.ctx.setLineDash([]);
        });

        // Update floating toolbar position
        this.updateFloatingToolbar();
    }

    drawHandle(x, y) {
        this.ctx.shadowBlur = 0;
        this.ctx.fillStyle = '#ffffff';
        this.ctx.strokeStyle = '#00aaff';
        this.ctx.lineWidth = 2;
        this.ctx.beginPath();
        this.ctx.arc(x, y, 5, 0, Math.PI * 2);
        this.ctx.fill();
        this.ctx.stroke();
    }

    updateFloatingToolbar() {
        if (this.selectedIndex < 0 || !this.floatingToolbar) {
            if (this.floatingToolbar) {
                this.floatingToolbar.style.display = 'none';
            }
            return;
        }

        const d = this.drawings[this.selectedIndex];
        const rect = this.canvas.getBoundingClientRect();

        // Calculate position based on drawing type
        let x, y;
        switch (d.type) {
            case 'line':
            case 'ray':
                x = (d.x1 + d.x2) / 2;
                y = Math.min(d.y1, d.y2);
                break;
            case 'hline':
                x = this.canvas.width / 2;
                y = d.y;
                break;
            case 'vline':
                x = d.x;
                y = 50;
                break;
            case 'rect':
                x = d.x + d.w / 2;
                y = d.y;
                break;
            case 'cross':
                x = d.x;
                y = d.y;
                break;
            case 'fib':
                x = this.canvas.width / 2;
                y = Math.min(d.y1, d.y2);
                break;
            default:
                x = 100;
                y = 100;
        }

        // Position toolbar above the drawing
        const toolbarX = rect.left + x - 100; // Center the toolbar
        const toolbarY = rect.top + y - 45; // Above the drawing

        this.floatingToolbar.style.left = Math.max(10, toolbarX) + 'px';
        this.floatingToolbar.style.top = Math.max(10, toolbarY) + 'px';
        this.floatingToolbar.style.display = 'flex';
    }

    drawFibonacci(y1, y2, isSelected) {
        const levels = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1];
        const colors = ['#ff0000', '#ff6600', '#ffaa00', '#00ff00', '#00aaff', '#0066ff', '#ff0000'];
        const dy = y2 - y1;

        if (isSelected) {
            this.ctx.shadowColor = '#ffffff';
            this.ctx.shadowBlur = 4;
        }

        levels.forEach((lvl, i) => {
            const y = y1 + dy * lvl;
            this.ctx.strokeStyle = colors[i];
            this.ctx.lineWidth = isSelected ? 3 : 2;
            this.ctx.beginPath();
            this.ctx.moveTo(0, y);
            this.ctx.lineTo(this.canvas.width, y);
            this.ctx.stroke();

            this.ctx.fillStyle = colors[i];
            this.ctx.font = '10px monospace';
            this.ctx.shadowBlur = 0;
            this.ctx.fillText((lvl * 100).toFixed(1) + '%', 5, y - 3);
        });

        this.ctx.shadowBlur = 0;
    }

    getMousePos(e) {
        const rect = this.canvas.getBoundingClientRect();
        return {
            x: e.clientX - rect.left,
            y: e.clientY - rect.top
        };
    }

    onMouseDown(e) {
        const pos = this.getMousePos(e);

        // In select mode, try to select/drag
        if (this.currentTool === 'select') {
            const hitIndex = this.hitTest(pos.x, pos.y);

            if (hitIndex >= 0) {
                this.selectedIndex = hitIndex;
                this.isDragging = true;
                this.dragOffsetX = pos.x;
                this.dragOffsetY = pos.y;
                this.canvas.style.cursor = 'move';
            } else {
                this.selectedIndex = -1;
            }
            this.redrawAll();
            return;
        }

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
        const pos = this.getMousePos(e);

        // Handle dragging selected drawing
        if (this.isDragging && this.selectedIndex >= 0) {
            const dx = pos.x - this.dragOffsetX;
            const dy = pos.y - this.dragOffsetY;
            this.moveDrawing(this.selectedIndex, dx, dy);
            this.dragOffsetX = pos.x;
            this.dragOffsetY = pos.y;
            this.redrawAll();
            return;
        }

        // In select mode, check hover state
        if (this.currentTool === 'select' && !this.isDrawing) {
            const hitIndex = this.hitTest(pos.x, pos.y);
            if (hitIndex !== this.hoveredIndex) {
                this.hoveredIndex = hitIndex;
                this.canvas.style.cursor = hitIndex >= 0 ? 'pointer' : 'default';
                this.redrawAll();
            }
            return;
        }

        if (!this.isDrawing) return;

        // Preview drawing
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

    moveDrawing(index, dx, dy) {
        const d = this.drawings[index];

        switch (d.type) {
            case 'line':
            case 'ray':
                d.x1 += dx; d.y1 += dy;
                d.x2 += dx; d.y2 += dy;
                break;
            case 'hline':
                d.y += dy;
                break;
            case 'vline':
                d.x += dx;
                break;
            case 'rect':
                d.x += dx; d.y += dy;
                break;
            case 'cross':
                d.x += dx; d.y += dy;
                break;
            case 'fib':
                d.y1 += dy; d.y2 += dy;
                break;
        }
    }

    onMouseUp(e) {
        if (this.isDragging) {
            this.isDragging = false;
            this.canvas.style.cursor = 'default';
            return;
        }

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
        this.isDragging = false;
        this.hoveredIndex = -1;
    }

    onDoubleClick(e) {
        const pos = this.getMousePos(e);
        const hitIndex = this.hitTest(pos.x, pos.y);

        if (hitIndex >= 0) {
            // Open properties dialog (simplified - just toggle dashed)
            this.drawings[hitIndex].dashed = !this.drawings[hitIndex].dashed;
            this.redrawAll();
        }
    }

    onContextMenu(e) {
        e.preventDefault();
        const pos = this.getMousePos(e);
        const hitIndex = this.hitTest(pos.x, pos.y);

        if (hitIndex >= 0) {
            this.selectedIndex = hitIndex;
            this.redrawAll();
            this.showContextMenu(e.clientX, e.clientY);
        }
    }

    onKeyDown(e) {
        const key = e.key.toLowerCase();

        const shortcuts = {
            'v': 'cursor',
            's': 'select',
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
        } else if ((key === 'delete' || key === 'backspace') && this.selectedIndex >= 0) {
            this.deleteSelected();
        } else if ((key === 'delete' || key === 'backspace') && this.selectedIndex < 0) {
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
