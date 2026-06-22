for m_name, m_obj in self.env.items():
    if not m_obj._auto or m_obj._transient:
        continue
    for f_name, field in m_obj._fields.items():
        if field.type == 'many2one' and field.comodel_name == 'res.partner':
            try:
                recs = m_obj.search([(f_name, '=', 27)])
                if recs:
                    print('FOUND:', m_name, f_name, recs.ids)
            except Exception as e:
                pass
