# Customer Escalation: Undo/Redo History Corruption

## Zendesk Ticket #58234

**Priority**: Urgent
**Customer**: DesignStudio Pro (Enterprise Tier)
**Account Value**: $180,000 ARR
**CSM**: Michael Torres
**Created**: 2024-02-18 10:15 UTC
**Status**: Escalated to Engineering

---

## Customer Report

> We're experiencing a critical issue with the undo/redo functionality. When users undo an action, they don't get the previous state - they get some corrupted version that includes changes made AFTER the undo point. This is causing our designers to lose hours of work.
>
> This is a dealbreaker for us. Our team relies heavily on undo to iterate on designs. If we can't trust it, we can't use CollabCanvas.

### Reported Symptoms

1. **Undo Restores Wrong State**: Pressing Ctrl+Z doesn't restore the previous state - it restores a state that includes later modifications.

2. **Redo Shows Future Changes**: After undo, redo sometimes shows elements that haven't been created yet (from a collaborator's later changes).

3. **History "Leaks" Between Sessions**: Changes made by User B seem to contaminate User A's undo history.

4. **Cascading Corruption**: After one corrupted undo, all subsequent undo/redo operations return garbage.

---

## Reproduction Steps (from QA)

### Scenario 1: Basic Undo Corruption

1. User opens board, creates Rectangle A
2. User creates Rectangle B
3. User modifies Rectangle B (change color to red)
4. User presses Undo (expects B to return to original color)
5. **Actual**: B is now ALSO red (same as current state)

### Scenario 2: Object Reference Issue

```
Step 1: Create element with position {x: 100, y: 100}
        -> History: [state with x:100, y:100]

Step 2: Move element to {x: 200, y: 200}
        -> History: [state with x:200, y:200, state with x:200, y:200]
        (Bug: Both history entries now show the SAME position!)

Step 3: Press Undo
        -> Expected: Element at {x: 100, y: 100}
        -> Actual: Element at {x: 200, y: 200} (undo did nothing)
```

### Scenario 3: State Mutation Across Boards

1. User A joins Board 1, creates Element X
2. User A switches to Board 2, creates Element Y
3. User A presses Undo on Board 2
4. **Expected**: Element Y is removed from Board 2
5. **Actual**: Element X is affected on Board 1 (!)

---

## Technical Details from Browser Console

### Debug Output During Undo

```javascript
// Console output from debug mode
[HISTORY] pushState called for board-123
[HISTORY] State to push: {elements: {...}, version: 45}
[HISTORY] Stack after push: length=5

// ... user makes more changes ...

[HISTORY] undo called for board-123
[HISTORY] Retrieved state: {elements: {...}, version: 48}
// BUG: Retrieved version 48, but we pushed version 45!

[HISTORY] Applying previous state
[HISTORY] Applied state has same elements as current!
```

### Memory Reference Debug

```javascript
// Added debugging to history service
const state1 = historyService.undoStacks.get('board-123')[0];
const state2 = historyService.undoStacks.get('board-123')[1];

console.log(state1 === state2);  // true (!)
console.log(state1.elements === state2.elements);  // true (!!)

// All states in the stack are the SAME OBJECT REFERENCE
```

---

## Internal Slack Thread

**#eng-frontend** - February 18, 2024

**@dev.emma** (10:45):
> Got a P1 from DesignStudio Pro about undo/redo. Sounds like a state mutation issue.

**@dev.marcus** (10:52):
> I think I see the problem. In `history.service.js`, we're pushing states directly without copying:
```javascript
pushState(boardId, state) {
  undoStack.push(state);  // This is a reference, not a copy!
}
```

**@dev.emma** (10:58):
> Oh no. So when the state object gets modified later, ALL the history entries get modified because they're all pointing to the same object.

**@dev.marcus** (11:02):
> Exactly. Same issue in `undo()`:
```javascript
// BUG: Returns reference that caller will mutate
const previousState = undoStack.pop();
return previousState;
```

**@dev.sarah** (11:08):
> We need JSON.parse(JSON.stringify(state)) or a proper deep clone. The spread operator `{...state}` won't work because elements is nested.

**@dev.emma** (11:12):
> This would also explain the CRDT merge issues. In `crdt.service.js`, we're doing:
```javascript
const merged = { ...localState };  // Shallow copy
merged[key] = { ...merged[key], ...remoteState[key] };  // Still shallow!
```

**@dev.marcus** (11:15):
> The state object is:
```javascript
{
  version: 45,
  elements: {
    'elem-1': { x: 100, y: 100, style: { color: 'red' } }
  }
}
```
A shallow copy doesn't copy the `style` object inside elements.

**@dev.sarah** (11:20):
> So if someone changes `state.elements['elem-1'].style.color = 'blue'`, it affects ALL states in history because they share the same nested object references.

---

## User-Visible Bugs

1. **Undo "Does Nothing"**: User clicks undo, nothing visible changes because history and current state are the same object.

2. **Undo Makes Things Worse**: Sometimes undo appears to apply FUTURE changes because a collaborator mutated the shared state object.

3. **Redo Creates Duplicates**: Redo might show the same element twice if the state was partially cloned.

4. **"Time Travel" Bug**: Users report elements "jumping" to old positions when other users make changes (because history states are being mutated).

## Browser Console Errors

```
[CollabCanvas] Warning: Undo returned state identical to current
[CollabCanvas] Warning: History state.version mismatch: expected 42, got 47
[CollabCanvas] Error: Cannot read property 'x' of undefined
  at applyHistoryState (history.service.js:67)
  at undo (history.service.js:52)
```

## Impact Assessment

- **Users Affected**: All users attempting undo/redo
- **Severity**: High - core functionality broken
- **Workaround**: None - users cannot safely use undo
- **Revenue Risk**: Customer threatening to cancel contract

## Files to Investigate

- `src/services/canvas/history.service.js` - Storing references instead of copies
- `src/services/canvas/crdt.service.js` - Shallow copy in mergeState

---

**Status**: ESCALATED
**Assigned**: @frontend-team, @sync-team
**Deadline**: EOD February 19, 2024
**Customer Call**: Scheduled for February 20, 2024 09:00 PST
