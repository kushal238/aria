## Project Vision

In India, clinic doctors still hand physical prescriptions to patients. This physical prescription is the only signature of the interaction between the doctor and their patient. We want to change that.

We are creating a digital medical record of each doctor-patient interaction. The doctor will prescribe the patient on the doctor app, the patient will receive the prescription on the patients app, and we will maintain each record for both the parties to review anytime and have a history of.

Additionally, we can deploy AI agents that can order based on the prescriptions, help doctors find patterns, etc.

## Core Use Cases

This backend is designed to support a multi-portal system for doctors and patients with the following core functionality:

1.  **Unified User Portal:** A single `Users` table will manage the core identity for all individuals. A user can have multiple roles (e.g., `"DOCTOR"`, `"PATIENT"`), allowing a doctor to also be a patient within the system.

2.  **Digital Prescriptions:** Doctors can create, view, and manage digital prescriptions for their patients. The full history of all prescriptions is maintained and is accessible to both the prescribing doctor and the patient at any time.

3.  **Medical Record Uploads:** Patients have the ability to upload supplementary medical records, such as lab scans, hospital reports, and other documents. This provides a richer medical history for the doctor to consult. This is achieved using a combination of Amazon S3 for file storage and DynamoDB for metadata.

4.  **AI and Analytics:** The architecture is designed to support future AI integrations. By streaming data from the primary database to a dedicated analytics engine, we can enable complex queries and AI-driven insights without impacting the performance of the live application.
