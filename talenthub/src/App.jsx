import React, { useState, useRef, useEffect } from "react";
import axios from "axios";

const API_BASE = "http://localhost:8000";

export default function App() {
  const [jdFiles, setJdFiles] = useState([]);
  const [candidates, setCandidates] = useState([]);
  const [hoverJD, setHoverJD] = useState(false);
  const [hoverCV, setHoverCV] = useState(false);
  const [jdLoading, setJdLoading] = useState(false);
  const [cvLoading, setCvLoading] = useState(false);
  const [selectedJob, setSelectedJob] = useState(null);
  const [selectedCandidate, setSelectedCandidate] = useState(null);
  const [jobText, setJobText] = useState("");
  const [candidateText, setCandidateText] = useState("");
  const [jobLoading, setJobLoading] = useState(false);
  const [candidateLoading, setCandidateLoading] = useState(false);
  const jdInputRef = useRef();
  const cvInputRef = useRef();
  const [search, setSearch] = useState("");
  const [cvSearch, setCvSearch] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    fetchJobs();
    fetchCandidates();
  }, []);

  const fetchJobs = async () => {
    try {
      const res = await axios.get(`${API_BASE}/jobs/all`);
      console.log("Raw jobs data:", res.data);
      
      const jobs = (res.data || []).map(job => ({
        ...job,
        file_id: job.file_id || String(job._id),
        parse_score: typeof job.parse_score === 'number' ? job.parse_score : Number(job.parse_score) || 0
      }));
      
      setJdFiles(jobs);
    } catch (err) {
      console.error("Failed to fetch jobs:", err);
      setError("Failed to fetch jobs: " + (err.response?.data?.error || err.message));
    }
  };

  const fetchCandidates = async () => {
    try {
      const res = await axios.get(`${API_BASE}/candidates/all`);
      console.log("Raw candidates data:", res.data);
      
      const candidates = (res.data || []).map(candidate => ({
        ...candidate,
        candidate_id: candidate.candidate_id || String(candidate._id),
        parse_score: typeof candidate.parse_score === 'number' ? candidate.parse_score : Number(candidate.parse_score) || 0
      }));
      
      setCandidates(candidates);
    } catch (err) {
      console.error("Failed to fetch candidates:", err);
      setError("Failed to fetch candidates: " + (err.response?.data?.error || err.message));
    }
  };

  const uploadFiles = async (files) => {
    setJdLoading(true);
    setError("");
    
    for (let file of files) {
      // Validate file type
      if (!file.type.includes('pdf') && !file.type.includes('word')) {
        setError(`${file.name} is not a supported file type. Only PDF and DOCX files are allowed.`);
        continue;
      }

      const formData = new FormData();
      formData.append("file", file);
      
      try {
        const response = await axios.post(`${API_BASE}/jobs/parse`, formData, {
          headers: { "Content-Type": "multipart/form-data" },
        });
        console.log("Uploaded:", file.name, response.data);
      } catch (err) {
        const errorMessage = err.response?.data?.error || err.message || "Upload failed";
        setError(`Failed to upload ${file.name}: ${errorMessage}`);
        console.error("Upload failed:", err.response?.data || err);
      }
    }
    
    await fetchJobs();
    setJdLoading(false);
  };

  const uploadCVs = async (files) => {
    setCvLoading(true);
    setError("");
    
    for (let file of files) {
      if (!file.type.includes('pdf') && !file.type.includes('word')) {
        setError(`${file.name} is not a supported file type. Only PDF and DOCX files are allowed.`);
        continue;
      }

      const formData = new FormData();
      formData.append("file", file);
      
      try {
        const response = await axios.post(`${API_BASE}/candidates/parse`, formData, {
          headers: { "Content-Type": "multipart/form-data" },
        });
        console.log("Uploaded CV:", file.name, response.data);
      } catch (err) {
        const errorMessage = err.response?.data?.error || err.message || "Upload failed";
        setError(`Failed to upload ${file.name}: ${errorMessage}`);
        console.error("Upload failed:", err.response?.data || err);
      }
    }
    
    await fetchCandidates();
    setCvLoading(false);
  };

  const deleteJob = async (fileId) => {
    try {
      const response = await axios.delete(`${API_BASE}/jobs/${fileId}`);
      if (response.status === 200) {
        await fetchJobs();
        if (selectedJob?.file_id === fileId) {
          setSelectedJob(null);
          setJobText("");
        }
      } else {
        setError(`Failed to delete job: ${response.data?.error || 'Unknown error'}`);
      }
    } catch (err) {
      console.error("Delete failed:", err);
      setError(`Failed to delete job: ${err.response?.data?.error || err.message}`);
    }
  };

  const deleteAllJobs = async () => {
    if (!window.confirm("Are you sure you want to delete all job descriptions?")) return;
    
    try {
      setJdLoading(true);
      setError("");

      // Get current jobs
      const res = await axios.get(`${API_BASE}/jobs/all`);
      const jobs = res.data || [];

      if (jobs.length === 0) {
        setError("No jobs to delete");
        return;
      }

      // Delete jobs one by one
      let deletedCount = 0;
      let failedCount = 0;

      for (const job of jobs) {
        try {
          // Ensure we have a valid ID to use
          const jobId = job.file_id || job._id;
          if (!jobId) {
            console.error(`Job ${job.filename} has no valid ID`);
            failedCount++;
            continue;
          }

          // Convert ObjectId to string if needed
          const id = typeof jobId === 'object' ? jobId.toString() : jobId;
          
          await axios.delete(`${API_BASE}/jobs/${id}`);
          console.log(`Successfully deleted job: ${job.filename}`);
          deletedCount++;
        } catch (err) {
          console.error(`Failed to delete job ${job.filename}:`, err);
          failedCount++;
        }
      }

      // Clear selected job and text if any job was deleted
      if (deletedCount > 0) {
        setSelectedJob(null);
        setJobText("");
      }
      
      // Refresh the jobs list
      await fetchJobs();

      // Show summary
      if (failedCount > 0) {
        setError(`Deleted ${deletedCount} jobs, but failed to delete ${failedCount} jobs`);
      } else if (deletedCount > 0) {
        setError(`Successfully deleted all ${deletedCount} jobs`);
        // Clear error after 3 seconds if successful
        setTimeout(() => setError(""), 3000);
      } else {
        setError("No jobs were deleted");
      }
    } catch (err) {
      console.error("Delete all failed:", err);
      setError(`Failed to delete all jobs: ${err.response?.data?.error || err.message}`);
    } finally {
      setJdLoading(false);
    }
  };

  const deleteCandidate = async (candidateId) => {
    try {
      const response = await axios.delete(`${API_BASE}/candidates/${candidateId}`);
      if (response.status === 200) {
        await fetchCandidates();
        if (selectedCandidate?.candidate_id === candidateId) {
          setSelectedCandidate(null);
          setCandidateText("");
        }
      } else {
        setError(`Failed to delete candidate: ${response.data?.error || 'Unknown error'}`);
      }
    } catch (err) {
      console.error("Delete failed:", err);
      setError(`Failed to delete candidate: ${err.response?.data?.error || err.message}`);
    }
  };

  const deleteAllCandidates = async () => {
    if (!window.confirm("Are you sure you want to delete all candidate CVs?")) return;
    
    try {
      setCvLoading(true);
      setError("");

      const res = await axios.get(`${API_BASE}/candidates/all`);
      const candidates = res.data || [];

      if (candidates.length === 0) {
        setError("No candidates to delete");
        return;
      }

      let deletedCount = 0;
      let failedCount = 0;

      for (const candidate of candidates) {
        try {
          const candidateId = candidate.candidate_id || candidate._id;
          if (!candidateId) {
            console.error(`Candidate ${candidate.filename} has no valid ID`);
            failedCount++;
            continue;
          }

          const id = typeof candidateId === 'object' ? candidateId.toString() : candidateId;
          await axios.delete(`${API_BASE}/candidates/${id}`);
          console.log(`Successfully deleted candidate: ${candidate.filename}`);
          deletedCount++;
        } catch (err) {
          console.error(`Failed to delete candidate ${candidate.filename}:`, err);
          failedCount++;
        }
      }

      if (deletedCount > 0) {
        setSelectedCandidate(null);
        setCandidateText("");
      }
      
      await fetchCandidates();

      if (failedCount > 0) {
        setError(`Deleted ${deletedCount} candidates, but failed to delete ${failedCount} candidates`);
      } else if (deletedCount > 0) {
        setError(`Successfully deleted all ${deletedCount} candidates`);
        setTimeout(() => setError(""), 3000);
      } else {
        setError("No candidates were deleted");
      }
    } catch (err) {
      console.error("Delete all failed:", err);
      setError(`Failed to delete all candidates: ${err.response?.data?.error || err.message}`);
    } finally {
      setCvLoading(false);
    }
  };

  const handleDrop = (e, type) => {
    e.preventDefault();
    const files = e.dataTransfer.files;
    if (type === "jd") setHoverJD(false);
    else setHoverCV(false);
    if (files.length) uploadFiles(files);
  };

  const handleBrowse = () => jdInputRef.current.click();

  const handleFileSelect = (e) => {
    const files = e.target.files;
    if (files.length) uploadFiles(files);
  };

  const handleSelectJob = async (job) => {
    if (!job?.file_id) {
      console.error("Invalid job selected:", job);
      setError("Invalid job selected");
      return;
    }

    setSelectedJob(job);
    setJobLoading(true);
    setJobText("");
    try {
      // Try to fetch using file_id
      const res = await axios.get(`${API_BASE}/jobs/${job.file_id}/text`);
      if (res.data?.text) {
        setJobText(res.data.text);
      } else {
        setError("No text content available for this job");
        setJobText("No job description available.");
      }
    } catch (err) {
      console.error("Failed to fetch job text:", err);
      const errorMessage = err.response?.data?.error || err.message || "Failed to load job description";
      setError(`Error: ${errorMessage}`);
      setJobText("Failed to load job description.");
    } finally {
      setJobLoading(false);
    }
  };

  const handleSelectCandidate = async (candidate) => {
    if (!candidate?.candidate_id) {
      console.error("Invalid candidate selected:", candidate);
      setError("Invalid candidate selected");
      return;
    }

    setSelectedCandidate(candidate);
    setCandidateLoading(true);
    setCandidateText("");
    try {
      const res = await axios.get(`${API_BASE}/candidates/${candidate.candidate_id}/text`);
      if (res.data?.text) {
        setCandidateText(res.data.text);
      } else {
        setError("No text content available for this candidate");
        setCandidateText("No CV content available.");
      }
    } catch (err) {
      console.error("Failed to fetch candidate text:", err);
      const errorMessage = err.response?.data?.error || err.message || "Failed to load CV";
      setError(`Error: ${errorMessage}`);
      setCandidateText("Failed to load CV.");
    } finally {
      setCandidateLoading(false);
    }
  };

  const filteredJobs = jdFiles.filter(job => job.filename.toLowerCase().includes(search.toLowerCase()));

  return (
    <div className="min-h-screen bg-gray-100">
      <nav className="flex justify-between items-center bg-white px-6 py-3 shadow-sm">
        <div className="text-xl font-bold text-gray-800">TalentHub</div>
        <div className="flex gap-6 items-center">
          {["Match Workspace", "Analytics", "Settings"].map((item, index) => (
            <a key={index} href="#" className="text-gray-600 hover:text-blue-600">{item}</a>
          ))}
          <div className="w-8 h-8 bg-emerald-400 rounded-full text-white flex items-center justify-center">U</div>
        </div>
      </nav>

      {error && (
        <div className="fixed top-4 right-4 bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
          <span className="block sm:inline">{error}</span>
          <button onClick={() => setError("")} className="absolute top-0 right-0 px-4 py-3">
            <span className="text-2xl">&times;</span>
          </button>
        </div>
      )}

      <div className="grid grid-cols-3 gap-2 p-4">
        {/* JD Upload + List Panel */}
        <div
          onDragOver={(e) => { e.preventDefault(); setHoverJD(true); }}
          onDragLeave={() => setHoverJD(false)}
          onDrop={(e) => handleDrop(e, "jd")}
          className={`border-r pr-4 ${hoverJD ? "bg-blue-50" : "bg-white"}`}
        >
          <h2 className="text-lg font-semibold mb-2 flex justify-between items-center">
            Job Descriptions
            {jdFiles.length > 0 && (
              <button onClick={deleteAllJobs} className="text-xs text-red-500 hover:underline">
                Delete All
              </button>
            )}
          </h2>

          <input
            type="text"
            placeholder="Search jobs..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full p-2 mb-3 border border-gray-300 rounded"
          />

          <div
            className={`border-2 border-dashed p-4 rounded-md text-center cursor-pointer ${
              hoverJD ? "border-blue-500 bg-blue-100" : "border-blue-300"
            }`}
            onClick={handleBrowse}
          >
            Drag & drop job descriptions here or <span className="text-blue-600 underline">browse</span>
            <input ref={jdInputRef} type="file" multiple className="hidden" onChange={handleFileSelect} />
          </div>

          {jdLoading && <p className="text-sm mt-2 text-blue-500">Uploading...</p>}
          {filteredJobs.length === 0 && !jdLoading && (
            <p className="text-xs text-gray-400 text-center mt-4">No job descriptions uploaded yet.</p>
          )}

          <div className="mt-4 space-y-2 max-h-[400px] overflow-y-auto pr-2">
            {filteredJobs.map((job) => (
              <div
                key={job.file_id}
                onClick={() => handleSelectJob(job)}
                className={`cursor-pointer bg-white rounded p-3 border transition flex justify-between items-start ${
                  selectedJob?.file_id === job.file_id ? "border-blue-500 ring-1 ring-blue-300" : "border-gray-200 hover:shadow-md"
                }`}
              >
                <div>
                  <h3 className="text-sm font-medium text-gray-800 truncate">{job.filename}</h3>
                  <p className="text-xs text-gray-500">
                    {(job.file_type.includes("pdf") ? "PDF" : job.file_type.includes("word") ? "DOCX" : "Unknown")} • 
                    <span className={`${job.parse_score >= 80 ? 'text-green-600' : job.parse_score >= 50 ? 'text-yellow-600' : 'text-red-600'}`}>
                      Score: {Math.round(job.parse_score)}%
                    </span> • 
                    {job.word_count.toLocaleString()} words
                  </p>
                </div>
                <button
                  onClick={(e) => { e.stopPropagation(); deleteJob(job.file_id); }}
                  className="text-red-500 hover:text-red-700 ml-2"
                  title="Delete"
                >
                  🗑️
                </button>
              </div>
            ))}
          </div>
        </div>

        {/* JD Viewer Panel */}
        <div className="border-r px-4 text-sm text-gray-600 overflow-y-auto max-h-[600px]">
          <h2 className="text-lg font-semibold mb-2">Job Description Viewer</h2>
          {!selectedJob ? (
            <p className="italic text-sm text-gray-500">
              Select a job description from the left panel to view its content
            </p>
          ) : jobLoading ? (
            <p className="text-blue-500 text-sm">Loading extracted job description...</p>
          ) : (
            <div className="whitespace-pre-wrap text-sm text-gray-700">
              <h3 className="font-semibold text-base text-gray-800 mb-1">{selectedJob.filename}</h3>
              <p className="text-xs text-gray-500 mb-2">
                {(selectedJob.file_type.includes("pdf") ? "PDF" : selectedJob.file_type.includes("word") ? "DOCX" : "Unknown")} • 
                <span className={`${selectedJob.parse_score >= 80 ? 'text-green-600' : selectedJob.parse_score >= 50 ? 'text-yellow-600' : 'text-red-600'}`}>
                  Score: {Math.round(selectedJob.parse_score)}%
                </span> • 
                {selectedJob.word_count.toLocaleString()} words
              </p>
              <div>{jobText}</div>
            </div>
          )}
        </div>

        {/* CV Upload + List Panel */}
        <div
          onDragOver={(e) => { e.preventDefault(); setHoverCV(true); }}
          onDragLeave={() => setHoverCV(false)}
          onDrop={(e) => { e.preventDefault(); const files = e.dataTransfer.files; setHoverCV(false); if (files.length) uploadCVs(files); }}
          className={`border-l pl-4 ${hoverCV ? "bg-blue-50" : "bg-white"}`}
        >
          <h2 className="text-lg font-semibold mb-2 flex justify-between items-center">
            Candidate CVs
            {candidates.length > 0 && (
              <button onClick={deleteAllCandidates} className="text-xs text-red-500 hover:underline">
                Delete All
              </button>
            )}
          </h2>

          <input
            type="text"
            placeholder="Search CVs..."
            value={cvSearch}
            onChange={(e) => setCvSearch(e.target.value)}
            className="w-full p-2 mb-3 border border-gray-300 rounded"
          >
          </input>

          <div
            className={`border-2 border-dashed p-4 rounded-md text-center cursor-pointer ${
              hoverCV ? "border-blue-500 bg-blue-100" : "border-blue-300"
            }`}
            onClick={() => cvInputRef.current.click()}
          >
            Drag & drop CVs here or <span className="text-blue-600 underline">browse</span>
            <input ref={cvInputRef} type="file" multiple className="hidden" onChange={(e) => uploadCVs(e.target.files)} />
          </div>

          {cvLoading && <p className="text-sm mt-2 text-blue-500">Uploading...</p>}
          {candidates.length === 0 && !cvLoading && (
            <p className="text-xs text-gray-400 text-center mt-4">No CVs uploaded yet.</p>
          )}

          <div className="mt-4 space-y-2 max-h-[400px] overflow-y-auto pr-2">
            {candidates
              .filter(cv => cv.filename.toLowerCase().includes(cvSearch.toLowerCase()))
              .map((candidate) => (
                <div
                  key={candidate.candidate_id}
                  onClick={() => handleSelectCandidate(candidate)}
                  className={`cursor-pointer bg-white rounded p-3 border transition flex justify-between items-start ${
                    selectedCandidate?.candidate_id === candidate.candidate_id ? "border-blue-500 ring-1 ring-blue-300" : "border-gray-200 hover:shadow-md"
                  }`}
                >
                  <div>
                    <h3 className="text-sm font-medium text-gray-800 truncate">
                      {candidate.extracted_info?.full_name || candidate.filename}
                    </h3>
                    <p className="text-xs text-gray-500">
                      {(candidate.file_type.includes("pdf") ? "PDF" : candidate.file_type.includes("word") ? "DOCX" : "Unknown")} • 
                      <span className={`${candidate.parse_score >= 80 ? 'text-green-600' : candidate.parse_score >= 50 ? 'text-yellow-600' : 'text-red-600'}`}>
                        Score: {Math.round(candidate.parse_score)}%
                      </span> • 
                      {candidate.word_count.toLocaleString()} words
                    </p>
                  </div>
                  <button
                    onClick={(e) => { e.stopPropagation(); deleteCandidate(candidate.candidate_id); }}
                    className="text-red-500 hover:text-red-700 ml-2"
                    title="Delete"
                  >
                    🗑️
                  </button>
                </div>
              ))}
          </div>

          {selectedCandidate && (
            <div className="mt-4 border-t pt-4">
              <h3 className="text-sm font-semibold mb-2">Candidate Information</h3>
              {candidateLoading ? (
                <p className="text-blue-500 text-sm">Loading CV content...</p>
              ) : (
                <div className="text-sm text-gray-700 space-y-4">
                  {/* Basic Information */}
                  <div className="space-y-2">
                    <h4 className="font-medium text-gray-900">Basic Information</h4>
                    <div className="grid grid-cols-2 gap-2">
                      {selectedCandidate.extracted_info.full_name && (
                        <div>
                          <span className="text-gray-500">Name:</span> {selectedCandidate.extracted_info.full_name}
                        </div>
                      )}
                      {selectedCandidate.extracted_info.email && (
                        <div>
                          <span className="text-gray-500">Email:</span> {selectedCandidate.extracted_info.email}
                        </div>
                      )}
                      {selectedCandidate.extracted_info.phone && (
                        <div>
                          <span className="text-gray-500">Phone:</span> {selectedCandidate.extracted_info.phone}
                        </div>
                      )}
                      {selectedCandidate.extracted_info.location && (
                        <div>
                          <span className="text-gray-500">Location:</span> {selectedCandidate.extracted_info.location}
                        </div>
                      )}
                      {selectedCandidate.extracted_info.availability && (
                        <div>
                          <span className="text-gray-500">Availability:</span> {selectedCandidate.extracted_info.availability}
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Links */}
                  {(selectedCandidate.extracted_info.linkedin || selectedCandidate.extracted_info.github) && (
                    <div className="space-y-2">
                      <h4 className="font-medium text-gray-900">Links</h4>
                      <div className="flex gap-4">
                        {selectedCandidate.extracted_info.linkedin && (
                          <a href={selectedCandidate.extracted_info.linkedin} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
                            LinkedIn
                          </a>
                        )}
                        {selectedCandidate.extracted_info.github && (
                          <a href={selectedCandidate.extracted_info.github} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
                            GitHub
                          </a>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Summary */}
                  {selectedCandidate.extracted_info.summary && (
                    <div className="space-y-2">
                      <h4 className="font-medium text-gray-900">Summary</h4>
                      <p className="whitespace-pre-wrap">{selectedCandidate.extracted_info.summary}</p>
                    </div>
                  )}

                  {/* Skills */}
                  {selectedCandidate.extracted_info.skills?.length > 0 && (
                    <div className="space-y-2">
                      <h4 className="font-medium text-gray-900">Skills</h4>
                      <div className="flex flex-wrap gap-2">
                        {selectedCandidate.extracted_info.skills.map((skill, index) => (
                          <span key={index} className="bg-blue-100 text-blue-800 px-2 py-1 rounded text-xs">
                            {skill}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Education */}
                  {selectedCandidate.extracted_info.education?.length > 0 && (
                    <div className="space-y-2">
                      <h4 className="font-medium text-gray-900">Education</h4>
                      <div className="space-y-2">
                        {selectedCandidate.extracted_info.education.map((edu, index) => (
                          <div key={index} className="border-l-2 border-blue-200 pl-2">
                            <div className="font-medium">{edu.degree}</div>
                            <div className="text-gray-600">{edu.institution}</div>
                            <div className="text-gray-500 text-xs">{edu.year_completed}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Experience */}
                  {selectedCandidate.extracted_info.experience?.length > 0 && (
                    <div className="space-y-2">
                      <h4 className="font-medium text-gray-900">Experience</h4>
                      <div className="space-y-4">
                        {selectedCandidate.extracted_info.experience.map((exp, index) => (
                          <div key={index} className="border-l-2 border-blue-200 pl-2">
                            <div className="font-medium">{exp.job_title}</div>
                            <div className="text-gray-600">{exp.company}</div>
                            <div className="text-gray-500 text-xs">{exp.duration}</div>
                            {exp.responsibilities?.length > 0 && (
                              <ul className="mt-2 list-disc list-inside text-sm">
                                {exp.responsibilities.map((resp, i) => (
                                  <li key={i}>{resp}</li>
                                ))}
                              </ul>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Certifications */}
                  {selectedCandidate.extracted_info.certifications?.length > 0 && (
                    <div className="space-y-2">
                      <h4 className="font-medium text-gray-900">Certifications</h4>
                      <div className="space-y-2">
                        {selectedCandidate.extracted_info.certifications.map((cert, index) => (
                          <div key={index} className="border-l-2 border-blue-200 pl-2">
                            <div className="font-medium">{cert.name}</div>
                            <div className="text-gray-600">{cert.issuer}</div>
                            <div className="text-gray-500 text-xs">{cert.year}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Languages */}
                  {selectedCandidate.extracted_info.languages?.length > 0 && (
                    <div className="space-y-2">
                      <h4 className="font-medium text-gray-900">Languages</h4>
                      <div className="flex flex-wrap gap-2">
                        {selectedCandidate.extracted_info.languages.map((lang, index) => (
                          <span key={index} className="bg-gray-100 text-gray-800 px-2 py-1 rounded text-xs">
                            {lang}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}