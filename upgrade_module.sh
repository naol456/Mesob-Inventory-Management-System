#!/bin/bash

# Script to upgrade mesob_inventory_base module in all databases
# This will update the database schema with new fields

echo "Upgrading mesob_inventory_base module..."

# List of databases (add more if needed)
databases=("mesoobproo" "mesobauto" "mesoob")

for db in "${databases[@]}"; do
    echo ""
    echo "========================================="
    echo "Upgrading module in database: $db"
    echo "========================================="
    
    docker exec mesob-odoo odoo \
        -d "$db" \
        -u mesob_inventory_base \
        --stop-after-init \
        --log-level=warn \
        2>&1 | grep -E "Modules|Updated|registry|error|Error|ERROR"
    
    if [ $? -eq 0 ]; then
        echo "✅ Module upgraded successfully in $db"
    else
        echo "⚠️  Warning: Check output for $db"
    fi
done

echo ""
echo "========================================="
echo "Upgrade complete! Restarting Odoo..."
echo "========================================="

docker restart mesob-odoo

echo "✅ Done! Please wait 10 seconds and try accessing Odoo again."
