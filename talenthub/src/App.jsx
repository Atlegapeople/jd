import React, { useState, useRef, useEffect } from "react";
import axios from "axios";

const API_BASE = "http://localhost:8000";

export default function App() {
  const [jdFiles, setJdFiles] = useState([]);
  const [hoverJD, setHoverJD] = useState(false);
  const [hoverCV, setHoverCV] = useState(false);
  const [loading, setLoading] = useState(false);
  const [selectedJob, setSelectedJob] = useState(null);
  const [jobText, setJobText] = useState("");
  const [jobLoading, setJobLoading] = useState(false);
  const inputRef = useRef();
  const [search, setSearch] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    fetchJobs();
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

  const uploadFiles = async (files) => {
    setLoading(true);
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
    setLoading(false);
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
      setLoading(true);
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
      setLoading(false);
    }
  };

  const handleDrop = (e, type) => {
    e.preventDefault();
    const files = e.dataTransfer.files;
    if (type === "jd") setHoverJD(false);
    else setHoverCV(false);
    if (files.length) uploadFiles(files);
  };

  const handleBrowse = () => inputRef.current.click();

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
            <input ref={inputRef} type="file" multiple className="hidden" onChange={handleFileSelect} />
          </div>

          {loading && <p className="text-sm mt-2 text-blue-500">Uploading...</p>}
          {filteredJobs.length === 0 && !loading && (
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
      </div>
    </div>
  );
}