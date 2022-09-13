def remove_node_from_section(cls, node, category, migrate=False, use_migration_dict=True):
        """
        ClassMethod to remove a list of nodes from a list of categories within the config file. .
        """
        migration_dict = {}
        categories = [category, '{}_{}'.format('new', category)]
        if migrate:
            # Leaving only new_{category}
            del categories[categories.index(category)]
        categories += InventoryConfig.inventory_categories['provision']
        for node_key in node:
            for cat in categories:
                try:
                    cls.log.info("Removing {} from category {}".format(node_key, cat))
                    if migrate and use_migration_dict:
                        migration_dict.update({node_key: InventoryConfig.ansible_host_cfg[cat][node_key]})
                    del InventoryConfig.ansible_host_cfg[cat][node_key]
                except KeyError:
                    cls.log.debug("{} wasn't present within {} after all.".format(node_key, cat))
        if migrate:
            return migration_dict 