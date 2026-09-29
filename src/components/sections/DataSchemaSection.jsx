import React, { useState } from 'react';
import { schemaResources, schemaFields } from '../../data/siteData';
import './DataSchemaSection.css';

export default function DataSchemaSection() {
  const [activeResource, setActiveResource] = useState('orders');
  const schema = schemaFields[activeResource] || schemaFields.orders;

  return (
    <section className="data-schema section" id="data-resources" aria-label="Data schema">
      <div className="container">
        <div className="data-schema__header">
          <h2 className="data-schema__headline">
            The data your teams actually need.
          </h2>
          <p className="data-schema__sub">
            Make core commerce entities accessible through one consistent layer.
          </p>
          <p className="data-schema__tagline">
            Different source systems. Consistent business context.
          </p>
        </div>

        <div className="data-schema__explorer">
          {/* Sidebar */}
          <div className="data-schema__sidebar" role="tablist" aria-label="Resource types">
            <p className="data-schema__sidebar-label">RESOURCES</p>
            {schemaResources.map((resource) => {
              const isActive = activeResource === resource.id;
              return (
                <button
                  key={resource.id}
                  role="tab"
                  aria-selected={isActive}
                  className={`data-schema__resource-btn ${isActive ? 'data-schema__resource-btn--active' : ''}`}
                  onClick={() => setActiveResource(resource.id)}
                >
                  <span className="data-schema__resource-name">{resource.label}</span>
                  {isActive && (
                    <span className="data-schema__resource-dot" aria-hidden="true" />
                  )}
                </button>
              );
            })}
          </div>

          {/* Table */}
          <div className="data-schema__table-wrapper" role="tabpanel">
            <div className="data-schema__table-header">
              <div className="data-schema__table-title">
                <span className="data-schema__resource-title">{schema.title}</span>
                <span className="data-schema__resource-subtitle">{schema.subtitle}</span>
              </div>
              <span className="data-schema__field-count">{schema.totalFields} fields</span>
            </div>

            <div className="data-schema__table-cols">
              <span>FIELD_NAME</span>
              <span>TYPE</span>
              <span>NOTES</span>
            </div>

            <div className="data-schema__rows" key={activeResource}>
              {schema.fields.map((field) => (
                <div key={field.name} className="data-schema__row">
                  <span className="data-schema__field-name">{field.name}</span>
                  <span className="data-schema__field-type">{field.type}</span>
                  <span className="data-schema__field-notes">{field.notes}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
