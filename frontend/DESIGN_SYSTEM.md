# AI Sales Training Dashboard - Design Styling

## Technology Stack: React + Bootstrap 5.3.2

---

## 1. Color Palette

### Primary Colors
```css
--primary-gradient: linear-gradient(135deg, #1e293b 0%, #334155 50%, #475569 100%);
--success-color: #22c55e;
--success-dark: #16a34a;
--success-light: rgba(34, 197, 94, 0.1);
```

### Text Colors
```css
--text-primary: #ffffff;
--text-light: #e2e8f0;
--text-muted: #94a3b8;
--text-dark: #1e293b;
```

### Background Colors
```css
--card-bg: rgba(30, 41, 59, 0.95);
--card-bg-hover: rgba(34, 197, 94, 0.08);
--card-border: rgba(148, 163, 184, 0.4);
--overlay-bg: rgba(15, 23, 42, 0.95);
```

### Status Colors
```css
--error-color: #ef4444;
--warning-color: #f59e0b;
--info-color: #3b82f6;
--success-color: #22c55e;
```

---

## 2. Typography

### Font Stack
```css
font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
```

### Font Sizes & Weights
- **Display**: 2.5rem (40px) - Weight: 700
- **H1**: 2rem (32px) - Weight: 700
- **H2**: 1.75rem (28px) - Weight: 600
- **H3**: 1.5rem (24px) - Weight: 600
- **H4**: 1.25rem (20px) - Weight: 600
- **Body**: 1rem (16px) - Weight: 400
- **Small**: 0.875rem (14px) - Weight: 400
- **Caption**: 0.75rem (12px) - Weight: 500

### Text Shadows
```css
text-shadow: 0 1px 2px rgba(0, 0, 0, 0.5); /* For titles on dark backgrounds */
```

---

## 3. Component Specifications

### 3.1 Buttons

#### Primary Button
```css
.btn-custom-primary {
  background: linear-gradient(45deg, #22c55e, #16a34a);
  border: none;
  color: #ffffff;
  font-weight: 600;
  padding: 0.75rem 1.5rem;
  border-radius: 8px;
  transition: all 0.3s ease;
  box-shadow: 0 2px 4px rgba(34, 197, 94, 0.2);
}
```

#### Secondary Button
```css
.btn-custom-outline {
  background: transparent;
  border: 2px solid #22c55e;
  color: #22c55e;
  font-weight: 500;
  padding: 0.6rem 1.25rem;
  border-radius: 8px;
  transition: all 0.3s ease;
}
```

#### Button States
- **Hover**: `transform: translateY(-2px)` + enhanced shadow
- **Active**: `transform: translateY(0)`
- **Disabled**: `opacity: 0.6` + `cursor: not-allowed`

### 3.2 Cards

#### Persona Cards
```css
.persona-card {
  background: rgba(30, 41, 59, 0.95);
  border: 2px solid rgba(148, 163, 184, 0.4);
  border-radius: 16px;
  padding: 2rem;
  min-height: 240px;
  backdrop-filter: blur(15px);
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
}
```

#### Standard Cards
```css
.card-custom {
  background: rgba(15, 23, 42, 0.8);
  border: 1px solid rgba(148, 163, 184, 0.3);
  border-radius: 12px;
  backdrop-filter: blur(10px);
}
```

### 3.3 Navigation

#### Navbar
```css
.dashboard-navbar {
  background: rgba(15, 23, 42, 0.8);
  backdrop-filter: blur(10px);
  border-bottom: 1px solid rgba(148, 163, 184, 0.3);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}
```

### 3.4 Loading Components

#### Loading Overlay
```css
.loading-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(15, 23, 42, 0.95);
  backdrop-filter: blur(5px);
  z-index: 9999;
}
```

#### Progress Bar
```css
.progress-custom {
  background: rgba(148, 163, 184, 0.2);
  height: 8px;
  border-radius: 4px;
}

.progress-bar-custom {
  background: linear-gradient(90deg, #22c55e, #16a34a);
  border-radius: 4px;
}
```

---

## 4. Layout Guidelines

### 4.1 Spacing Scale
- **xs**: 0.25rem (4px)
- **sm**: 0.5rem (8px)
- **md**: 1rem (16px)
- **lg**: 1.5rem (24px)
- **xl**: 2rem (32px)
- **xxl**: 3rem (48px)

### 4.2 Border Radius
- **Small**: 8px (buttons, small cards)
- **Medium**: 12px (standard cards)
- **Large**: 16px (persona cards, modals)
- **Round**: 50% (avatars, circular buttons)

### 4.3 Shadows
```css
/* Subtle */
box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);

/* Standard */
box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);

/* Elevated */
box-shadow: 0 8px 25px rgba(0, 0, 0, 0.3);

/* Hover Effect */
box-shadow: 0 12px 30px rgba(34, 197, 94, 0.2);
```

---

## 5. Animation Guidelines

### 5.1 Transitions
```css
transition: all 0.3s ease; /* Standard transition */
transition: transform 0.2s ease; /* Quick transform */
```

### 5.2 Hover Effects
```css
/* Standard hover lift */
transform: translateY(-2px);

/* Strong hover lift */
transform: translateY(-4px);

/* Scale effect */
transform: scale(1.02);
```

### 5.3 Loading Animations
```css
@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}
```

---

## 6. Responsive Breakpoints

### Bootstrap 5 Breakpoints
- **xs**: <576px
- **sm**: ≥576px
- **md**: ≥768px
- **lg**: ≥992px
- **xl**: ≥1200px
- **xxl**: ≥1400px

### Component Responsive Behavior
- **Persona Cards**: 3 columns (lg+), 2 columns (md), 1 column (sm)
- **Stats Cards**: 4 columns (md+), 2 columns (sm)
- **Navigation**: Collapse on mobile

---

## 7. Accessibility Guidelines

### 7.1 Color Contrast
- **Minimum Contrast Ratio**: 4.5:1 for normal text
- **Enhanced Contrast Ratio**: 7:1 for important text
- **White text on dark backgrounds**: Used for maximum contrast

### 7.2 Focus States
```css
:focus {
  outline: 2px solid #22c55e;
  outline-offset: 2px;
}
```

### 7.3 Interactive Elements
- Minimum touch target: 44px × 44px
- Clear hover and focus states
- Descriptive aria-labels where needed

---

## 8. Performance Considerations

### 8.1 CSS Optimization
- Use CSS custom properties for consistent theming
- Minimize repaints with `transform` and `opacity`
- Use `backdrop-filter` sparingly for performance

### 8.2 Loading Strategy
- Show fallback content immediately
- Progressive enhancement with real data
- Maximum 2-second timeout for API requests

---

## 9. Component Library

### 9.1 Standard Components
- **PersonaCard**: Training partner selection cards
- **StatCard**: Progress statistics display
- **LoadingOverlay**: Full-screen loading with progress
- **ChatBubble**: Message display in training sessions
- **ProgressBar**: Custom styled progress indicators

### 9.2 Layout Components
- **DashboardNav**: Top navigation bar
- **SidebarNav**: Side navigation (if needed)
- **ContentArea**: Main content wrapper
- **GridLayout**: Responsive grid system

---

## 10. Usage Examples

### 10.1 Implementing a New Card Component
```jsx
<div className="card card-custom">
  <div className="card-header card-header-custom">
    <h5 className="mb-0 text-light">
      <i className="fas fa-icon me-2"></i>
      Card Title
    </h5>
  </div>
  <div className="card-body">
    <!-- Card content -->
  </div>
</div>
```

### 10.2 Color Usage
```jsx
// For titles - high contrast white
<h1 className="text-light">Main Title</h1>

// For persona names - white with shadow
<h2 className="persona-title">Persona Name</h2>

// For secondary text
<p className="text-muted">Secondary information</p>
```

---

## 11. Brand Guidelines

### 11.1 Logo Usage
- Primary logo color: `#22c55e` (Success Green)
- Minimum size: 24px height
- Clear space: 1x logo height on all sides

### 11.2 Icon Library
- **FontAwesome 6.4.2**: Primary icon source
- **Style**: Solid for primary actions, Regular for secondary
- **Size**: Consistent 1rem for inline, 1.5rem for standalone

---

## 12. Future Considerations

### 12.1 Dark/Light Mode Toggle
- Prepared CSS custom properties for easy theming
- Consider user preference detection
- Smooth transition between themes

### 12.2 Mobile App Adaptation
- Current design is mobile-first responsive
- Easy adaptation to React Native
- Consistent color scheme and spacing

### 12.3 Accessibility Enhancements
- High contrast mode support
- Screen reader optimization
- Keyboard navigation improvements

---

*This design styling guide ensures consistent, accessible, and performant user interfaces across the AI Sales Training Dashboard application.*