# Stock Classification and Automatic Item Coding

## 📋 Overview

This spec implements a three-level hierarchical stock identification system for the Mesob Inventory Management System (Odoo 19). The system enables automatic generation of unique item codes in format `MAJOR-SUB-SPECIFIC` (e.g., 4456-442-001) during receiving operations.

## ✅ Status

**Implementation**: ✅ Complete  
**Testing**: ⏳ Awaiting User Testing  
**Documentation**: ✅ Complete

## 🎯 Quick Links

| Document | Purpose | Audience |
|----------|---------|----------|
| [QUICK_START.md](QUICK_START.md) | Fast-track guide to upgrade and test | All users |
| [TEST_GUIDE.md](TEST_GUIDE.md) | Comprehensive test scenarios | Testers |
| [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) | Technical summary | Developers |
| [requirements.md](requirements.md) | Formal requirements | Product owners |
| [design.md](design.md) | Technical architecture | Developers |
| [tasks.md](tasks.md) | Implementation tasks | Project managers |

## 🚀 Getting Started

### Step 1: Upgrade Module

1. Open Odoo: http://localhost:8069
2. Navigate to **Apps**
3. Search: `mesob_inventory_base`
4. Click **Upgrade**
5. Wait for completion

### Step 2: Quick Test

Follow [QUICK_START.md](QUICK_START.md) to:
- Create your first sub-classifications
- Generate your first auto-coded items
- Verify bin cards and stock records

### Step 3: Comprehensive Testing

Follow [TEST_GUIDE.md](TEST_GUIDE.md) for:
- 12 test sessions covering all features
- Validation testing
- Performance testing
- Integration testing

## 📦 What's Included

### Models
- `mesob.inventory.sub.classification` - Sub-classification management
- `mesob.item.code.sequence` - Thread-safe sequence tracking
- Enhanced `mesob.inventory.item` - Added sub-classification link
- Enhanced `mesob.inventory.receiving.line` - Auto-generation logic

### Views
- Sub-Classification management views (list, form, search)
- Enhanced receiving line views with classification fields
- Smart buttons for viewing generated items

### Security
- PAO: Full control over sub-classifications
- Storekeeper: Read access and auto-generation capability
- System-managed sequence tracking

### Business Logic
- Automatic unique code generation (MAJOR-SUB-SPECIFIC format)
- Sequential numbering per major-sub combination
- Thread-safe sequence management with database locking
- Automatic bin card creation (1.0 per item)
- Automatic stock record + FIFO layer creation
- Dependent selection (sub-classifications filter by major)
- Comprehensive validation and error handling

## 🎓 Key Features

### Three-Level Classification
```
Major Classification (4 digits)
    └─ Sub-Classification (3 digits)
        └─ Specific Item Code (3 digits, auto-generated)
```

**Example**:
- Major: 4456 (Cleaning Materials)
- Sub: 442 (Soap)
- Generated Items: 4456-442-001, 4456-442-002, 4456-442-003...

### Dependent Selection
When user selects a major classification, only related sub-classifications appear in the dropdown.

### Auto-Generation
When receiving items:
1. Enable "Auto-Generate Items" checkbox
2. Select major and sub-classification
3. Set quantity accepted (e.g., 10)
4. System automatically creates 10 unique items with sequential codes

### Thread Safety
Multiple users can generate items simultaneously without code duplication, thanks to database row-level locking.

## 📊 Architecture

```
User Interface Layer
    ├─ Sub-Classification Views (PAO)
    └─ Receiving Views (Storekeeper)
        ↓
Business Logic Layer
    ├─ Classification Management
    ├─ Code Generation (with validation)
    ├─ Sequence Tracking (thread-safe)
    └─ Item Creation + Card Generation
        ↓
Data Model Layer
    ├─ mesob.inventory.sub.classification
    ├─ mesob.item.code.sequence
    ├─ mesob.inventory.item
    ├─ mesob.bin.card
    └─ mesob.stock.record.card
```

## 📋 Requirements Coverage

All 12 requirements implemented:

1. ✅ Major Classification Registration
2. ✅ Sub-Classification Registration  
3. ✅ Dependent Selection
4. ✅ Automatic Code Generation
5. ✅ Unique Item Creation
6. ✅ Automatic Bin Card Creation
7. ✅ Automatic Stock Record Creation
8. ✅ Item Code Format Validation
9. ✅ Auto-Generation Controls
10. ✅ Sequence Tracker Persistence
11. ✅ Error Handling
12. ✅ Security and Access Control

## 🧪 Testing Checklist

Use this checklist to track your testing progress:

### Core Functionality
- [ ] Create sub-classifications as PAO
- [ ] Validate code format (3 digits only)
- [ ] Test dependent selection (sub filters by major)
- [ ] Generate single item (verify code format)
- [ ] Generate multiple items (verify sequential codes)
- [ ] Verify bin card creation
- [ ] Verify stock record creation

### Validation
- [ ] Test missing major classification error
- [ ] Test missing sub-classification error
- [ ] Test zero quantity error
- [ ] Test negative price error
- [ ] Test missing UoM error

### Advanced
- [ ] Test sequence persistence across receivings
- [ ] Test different sub-classifications (independent sequences)
- [ ] Test mixed receiving lines (auto + manual)
- [ ] Test performance (50-100 items)
- [ ] Test concurrent operations (multiple users)

### Integration
- [ ] Verify Model 19 report displays generated items
- [ ] Verify DSR report handles rejections
- [ ] Test archiving sub-classifications
- [ ] Test smart buttons and counters

## 📈 Performance

Expected performance on standard hardware:

| Operation | Expected Time |
|-----------|--------------|
| Single item generation | 200-300ms |
| 10 items | 2-3 seconds |
| 50 items | 10-15 seconds |
| 100 items | 20-30 seconds |

**Note**: Performance optimization available if needed (Task 14).

## 🔒 Security

| Role | Sub-Classifications | Generated Items | Receiving |
|------|-------------------|-----------------|-----------|
| PAO | Create, Read, Update, Delete | Read | - |
| Storekeeper | Read | Create, Read | Full control |
| Base User | Read | Read | Read |

## 🐛 Known Limitations

1. **Sequence Limit**: 999 items per major-sub combination (3-digit limit)
2. **Performance**: Sequential creation may be slow for quantities > 100
3. **No Batch Mode**: Items created one-by-one (not batch optimized)

**Mitigation**: Task 14 provides optimization if performance issues arise.

## 📚 Documentation Structure

```
.kiro/specs/stock-classification-auto-coding/
├── README.md                    ← You are here
├── QUICK_START.md              ← Start here for testing
├── TEST_GUIDE.md               ← Comprehensive test scenarios
├── IMPLEMENTATION_SUMMARY.md   ← Technical implementation details
├── requirements.md             ← Formal requirements (EARS format)
├── design.md                   ← Technical architecture
└── tasks.md                    ← Task breakdown and status
```

## 🔄 Workflow

### PAO Workflow
1. Create major classifications (if not exists)
2. Create sub-classifications under majors
3. Configure codes and names
4. Monitor item counts

### Storekeeper Workflow
1. Create receiving order
2. Add receiving line
3. Enable "Auto-Generate Items"
4. Select major and sub-classification
5. Fill in quantity, price, description
6. Complete receiving
7. View generated items

### System Workflow
1. User completes receiving with auto-generate enabled
2. System validates required fields
3. For each quantity accepted:
   - Lock sequence tracker (thread-safe)
   - Get next sequence number
   - Format code: MAJOR-SUB-SPECIFIC
   - Create inventory item
   - Create bin card entry
   - Create stock record + FIFO layer
4. Link all items to receiving line
5. Display generated count

## 🎯 Success Criteria

- [x] Implementation complete
- [ ] Module upgrades successfully
- [ ] All test scenarios pass
- [ ] No duplicate codes generated
- [ ] Performance acceptable
- [ ] Integration verified
- [ ] User training complete

## 📞 Support

### Troubleshooting

**Module won't upgrade**
- Check Odoo logs: `docker logs odoo_container`
- Verify database connectivity
- Check for syntax errors in code

**Sub-classifications menu not showing**
- Clear browser cache (Ctrl+F5)
- Verify user has PAO or Storekeeper role
- Check module is fully upgraded

**Auto-generation not working**
- Verify all required fields filled
- Check Odoo logs for validation errors
- Verify receiving order in correct state

**Codes duplicating**
- Should not happen (row locking prevents this)
- If occurs, check database sequence integrity
- Review concurrent operation logs

### Getting Help

1. Review [QUICK_START.md](QUICK_START.md) and [TEST_GUIDE.md](TEST_GUIDE.md)
2. Check [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) for technical details
3. Review Odoo server logs for specific errors
4. Check [requirements.md](requirements.md) for expected behavior
5. Review [design.md](design.md) for architecture details

## 🎉 Next Steps

1. **Upgrade Module**: Follow instructions in QUICK_START.md
2. **Quick Test**: Complete the quick test scenario
3. **Comprehensive Testing**: Work through TEST_GUIDE.md
4. **Report Results**: Document any issues or unexpected behavior
5. **User Training**: Train PAO and Storekeeper users
6. **Go Live**: Deploy to production after successful testing

## 📝 Version History

- **v1.0.0** (2026-06-02): Initial implementation complete
  - All 12 requirements implemented
  - Comprehensive testing documentation provided
  - Ready for user acceptance testing

---

**Ready to start?** → Open [QUICK_START.md](QUICK_START.md)
