/** Content supplied by the project, rendered verbatim. No figures are invented here. */

export const SITE = {
  name: "EchoMiner",
  domain: "https://echominer.in",
  tagline: "Structured data from echocardiography reports",
  description:
    "EchoMiner converts semi-structured echocardiography PDF reports into analysis-ready " +
    "structured data. Developed under the DBT-BUILDER project at JSS Academy of Higher " +
    "Education and Research, Mysore.",
} as const;

export const CITATION = {
  doi: "10.5281/zenodo.21281483",
  url: "https://doi.org/10.5281/zenodo.21281483",
  apa:
    "B Manjunath, S. (2026). EchoMiner: source code for rule-based NLP extraction from " +
    "echocardiography PDF reports [Computer software]. Zenodo. https://doi.org/10.5281/zenodo.21281483",
  vancouver:
    "B Manjunath S. EchoMiner: source code for rule-based NLP extraction from echocardiography " +
    "PDF reports [Computer software]. Zenodo; 2026. Available from: https://doi.org/10.5281/zenodo.21281483",
  ieee:
    'S. B Manjunath, "EchoMiner: source code for rule-based NLP extraction from echocardiography ' +
    'PDF reports," Zenodo, 2026. [Online]. Available: https://doi.org/10.5281/zenodo.21281483',
  bibtex: `@software{echominer2026,
  author    = {B Manjunath, Suraj},
  title     = {EchoMiner: source code for rule-based NLP extraction from echocardiography PDF reports},
  year      = {2026},
  publisher = {Zenodo},
  doi       = {10.5281/zenodo.21281483},
  url       = {https://doi.org/10.5281/zenodo.21281483}
}`,
  ris: `TY  - COMP
AU  - B Manjunath, Suraj
TI  - EchoMiner: source code for rule-based NLP extraction from echocardiography PDF reports
PY  - 2026
PB  - Zenodo
DO  - 10.5281/zenodo.21281483
UR  - https://doi.org/10.5281/zenodo.21281483
ER  - `,
} as const;

export const DBT_PROGRAMME = {
  heading: "JSSAHER DBT BUILDER Project",
  body: [
    "JSS Academy of Higher Education & Research (JSSAHER) has been selected by the Department of " +
      "Biotechnology (DBT) to implement the prestigious DBT BUILDER (Boost to University " +
      "Interdisciplinary Life Science Departments for Education and Research) program.",
    "Backed by a ₹5 crore grant over five years, this initiative promotes interdepartmental " +
      "collaboration to nurture postgraduate talent and build a globally competitive bio-economy.",
  ],
  domains: [
    { n: "1", title: "Novel Biomarker and Therapeutics", note: "Metabolic disorders and cardiopulmonary disease." },
    { n: "2", title: "Nanotheranostics", note: "Advancing CVD disease management." },
    { n: "3", title: "Spatial Health Informatics and Management", note: "The domain EchoMiner is built in." },
  ],
  groupThree:
    "Group 3 leads the spatial health informatics domain and is the driving force behind the " +
    "development of AI_EchoMiner — a scalable, Python-based data extraction framework that " +
    "utilizes regular expressions and pandas to process complex healthcare data efficiently.",
} as const;

export const LEADERSHIP = [
  { name: "Dr. Prashant M Vishwanath", role: "Dean (Research), JSSAHER", email: "prashantv@jssuni.edu.in" },
  {
    name: "Dr. Rajesh Kumar Thimmulappa",
    role: "Principal Investigator | Professor, Dept. of Biochemistry, JSS Medical College",
    email: "kumar_rt@yahoo.com",
  },
  {
    name: "Dr. Madhu B",
    role: "Co-Principal Investigator | Professor & Head, Dept. of Community Medicine, JSS Medical College",
    email: "madhub@jssuni.edu.in",
  },
] as const;

export const TEAM = [
  {
    name: "Dr. Manjunatha M C",
    role: "Assistant Professor, Dept. of Community Medicine, JSS Medical College, Mysuru",
    email: "mcmanju1@gmail.com",
  },
  {
    name: "Suraj B M",
    role: "Senior Research Fellow, Dept. of Community Medicine, JSS Medical College, Mysuru",
    email: "surajbm@jssuni.edu.in",
  },
] as const;

export const CONTACT = {
  name: "Dr. Madhu B",
  lines: [
    "Professor & Head",
    "Co-Principal Investigator",
    "Department of Community Medicine",
    "JSS Medical College",
    "JSS Academy of Higher Education and Research",
    "Mysore, India",
  ],
  email: "madhub@jssuni.edu.in",
} as const;

export const PRIVACY_NOTICE =
  "The information collected through this portal is used solely for providing access to the " +
  "EchoMiner research platform and maintaining institutional usage records. User information " +
  "will be securely stored in accordance with applicable Government of India data protection " +
  "guidelines and institutional policies. The information will not be shared with any third " +
  "party except where required by law or institutional policy.";

export const AGREEMENT_TEXT = [
  "EchoMiner was developed at JSS Academy of Higher Education and Research (JSS AHER), Mysore.",
  "Copyright in the software belongs to JSS AHER.",
  "The software is intended for academic and research use.",
  "Users must acknowledge EchoMiner in all publications, theses, conference papers, reports and " +
    "scientific communications that use data generated through this tool.",
  "",
  "Suggested acknowledgement:",
  CITATION.apa,
].join("\n");

export const FEATURES = [
  {
    title: "Batch extraction",
    body: "Upload up to 20 echocardiography PDFs at once and receive one consolidated workbook.",
  },
  {
    title: "Rule-based and reproducible",
    body: "Deterministic regular-expression extraction. The same input always produces the same output, and every workbook records the engine version that produced it.",
  },
  {
    title: "Quality reporting",
    body: "Every export states pages read, reports detected in the source, rows returned, and any parse warnings, per file.",
  },
  {
    title: "Analysis-ready output",
    body: "Measurements arrive as numeric cells with a data dictionary sheet, ready for statistical software.",
  },
  {
    title: "Nothing retained",
    body: "Uploaded PDFs and generated files are deleted as soon as your download completes.",
  },
  {
    title: "Citable",
    body: "Archived on Zenodo with a DOI. Citation formats are included in every workbook.",
  },
] as const;

export const WORKFLOW = [
  { n: "01", title: "Register once", body: "Verify your email with a one-time code. Subsequent visits from the same device skip it." },
  { n: "02", title: "Upload reports", body: "Drop up to 20 PDF reports. Files are checked before anything is read." },
  { n: "03", title: "Extract", body: "The validated pipeline reads each report and maps it to the structured field set." },
  { n: "04", title: "Review", body: "Preview the extracted table and the per-file quality summary in the browser." },
  { n: "05", title: "Download and clear", body: "Take the branded workbook. Your files are removed from the server immediately." },
] as const;

export const FAQS = [
  {
    q: "What file formats can I upload?",
    a: "PDF only, up to 20 files per submission and 200 MB in total. The PDF must contain a text layer — scanned images without OCR cannot be read.",
  },
  {
    q: "Do I need to verify my email every time?",
    a: "No. A one-time code is required at first registration. After that, returning from the same browser restores your access silently. A new device or browser asks for one code again.",
  },
  {
    q: "What happens to the reports I upload?",
    a: "They are held only while your job runs and are deleted the moment your download completes. Jobs that are abandoned are swept automatically. Usage records such as file counts and timestamps are retained; report content is not.",
  },
  {
    q: "Is the extraction accurate?",
    a: "The pipeline is rule-based and deterministic, and it is validated against the report layouts it was built for. Every workbook includes a Quality sheet showing what was read from each file so you can verify the output rather than assume it.",
  },
  {
    q: "How should I cite EchoMiner?",
    a: "Use the citation in the How to Cite section, also included in every exported workbook in APA, Vancouver, IEEE, BibTeX and RIS.",
  },
  {
    q: "Who can use EchoMiner?",
    a: "Registration is open to researchers. Users are responsible for holding the appropriate ethical approvals for any data they process through the tool.",
  },
] as const;
