import React, { useState, useRef, useEffect } from "react";
import axios from "axios";

const API_BASE_URL = 'http://localhost:8000';

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error("Error caught by boundary:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="error-boundary">
          <h2>Something went wrong</h2>
          <p>{this.state.error?.message || 'An unexpected error occurred'}</p>
          <button onClick={() => this.setState({ hasError: false })}>
            Try again
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

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
  const [matchingResults, setMatchingResults] = useState(() => {
    // Try to get matching results from localStorage on initial load
    const savedResults = localStorage.getItem('matchingResults');
    return savedResults ? JSON.parse(savedResults) : null;
  });
  const [matchingLoading, setMatchingLoading] = useState(false);
  const jdInputRef = useRef();
  const cvInputRef = useRef();
  const [search, setSearch] = useState("");
  const [cvSearch, setCvSearch] = useState("");
  const [error, setError] = useState("");
  const [selectedMatch, setSelectedMatch] = useState(null);
  const [selectedCandidateForMatch, setSelectedCandidateForMatch] = useState(null);
  const [isMatching, setIsMatching] = useState(false);
  const [savedReports, setSavedReports] = useState([]);
  const [isGeneratingReport, setIsGeneratingReport] = useState(false);

  useEffect(() => {
    fetchJobs();
    fetchCandidates();
  }, []);

  useEffect(() => {
    if (matchingResults) {
      localStorage.setItem('matchingResults', JSON.stringify(matchingResults));
    } else {
      localStorage.removeItem('matchingResults');
    }
  }, [matchingResults]);

  const fetchJobs = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/jobs/all`);
      setJdFiles(response.data);
    } catch (error) {
      console.error('Failed to fetch jobs:', error);
      setError('Failed to fetch jobs. Please try again.');
    }
  };

  const fetchCandidates = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/candidates/all`);
      setCandidates(response.data);
    } catch (error) {
      console.error('Failed to fetch candidates:', error);
      setError('Failed to fetch candidates. Please try again.');
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
      formData.append("is_job", "true");
      
      try {
        const response = await axios.post(`${API_BASE_URL}/upload`, formData, {
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
      formData.append("is_job", "false");
      
      try {
        const response = await axios.post(`${API_BASE_URL}/upload`, formData, {
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

  const deleteJob = async (jobId) => {
    if (!jobId) {
      console.error("Invalid job ID:", jobId);
      setError("Cannot delete job: Invalid job ID");
      return;
    }

    try {
      const response = await axios.delete(`${API_BASE_URL}/jobs/${jobId}`);
      if (response.status === 200) {
        await fetchJobs();
        if (selectedJob?.job_id === jobId) {
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
      const res = await axios.get(`${API_BASE_URL}/jobs/all`);
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
          const jobId = job.job_id || job._id;
          if (!jobId) {
            console.error(`Job ${job.filename} has no valid ID`);
            failedCount++;
            continue;
          }

          // Convert ObjectId to string if needed
          const id = typeof jobId === 'object' ? jobId.toString() : jobId;
          
          await axios.delete(`${API_BASE_URL}/jobs/${id}`);
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
      const response = await axios.delete(`${API_BASE_URL}/candidates/${candidateId}`);
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

      const res = await axios.get(`${API_BASE_URL}/candidates/all`);
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
          await axios.delete(`${API_BASE_URL}/candidates/${id}`);
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

  const matchCandidates = async () => {
    if (!selectedJob) {
      setError('Please select a job description first');
      return;
    }

    try {
      setIsMatching(true);
      setError(null);

      const response = await axios.post(`${API_BASE_URL}/match`, {
        job_id: selectedJob.job_id,
        candidate_ids: selectedCandidateForMatch ? [selectedCandidateForMatch] : candidates.map(c => c.candidate_id)
      });

      if (response.data && response.data.matches) {
        const results = {
          matches: response.data.matches.map(match => ({
            ...match,
            candidate_name: candidates.find(c => c.candidate_id === match.candidate_id)?.extracted_info?.name || 'Unknown',
            python_score: match.python_score || 0,
            claude_score: match.claude_score || null,
            shortlist: match.shortlist || false,
            claude_analysis: match.claude_analysis || null
          }))
        };
        setMatchingResults(results);
        localStorage.setItem('matchingResults', JSON.stringify(results));
      } else {
        setError('Invalid response format from server');
      }
    } catch (error) {
      console.error('Failed to match candidates:', error);
      const errorMessage = error.response?.data?.detail?.message || 
                          error.response?.data?.detail || 
                          error.response?.data?.error || 
                          'Failed to match candidates. Please try again.';
      setError(errorMessage);
    } finally {
      setIsMatching(false);
    }
  };

  const handleSelectJob = async (job) => {
    setSelectedJob(job);
    setJobLoading(true);
    try {
      const response = await axios.get(`${API_BASE_URL}/jobs/${job.job_id}/text`);
      setJobText(response.data.text);
    } catch (err) {
      console.error("Failed to fetch job text:", err);
      setError("Failed to fetch job text: " + (err.response?.data?.error || err.message));
    } finally {
      setJobLoading(false);
    }
  };

  const handleSelectCandidate = async (candidate) => {
    setSelectedCandidate(candidate);
    setCandidateLoading(true);
    try {
      const response = await axios.get(`${API_BASE_URL}/candidates/${candidate.candidate_id}/text`);
      setCandidateText(response.data.text);
    } catch (err) {
      console.error("Failed to fetch candidate text:", err);
      setError("Failed to fetch candidate text: " + (err.response?.data?.error || err.message));
    } finally {
      setCandidateLoading(false);
    }
  };

  const handleSelectMatch = (match) => {
    setSelectedMatch(match);
  };

  const filteredJobs = jdFiles.filter(job => job.filename.toLowerCase().includes(search.toLowerCase()));

  const calculateYearsOfExperience = (experience) => {
    if (!experience || !Array.isArray(experience)) return 0;
    
    let totalYears = 0;
    const currentDate = new Date();
    const currentYear = currentDate.getFullYear();
    const currentMonth = currentDate.getMonth() + 1; // JavaScript months are 0-based

    experience.forEach((exp) => {
      const duration = exp.duration || '';
      console.log('Processing duration:', duration);

      // Handle "Present" or "Current" cases
      if (duration.toLowerCase().includes('present') || duration.toLowerCase().includes('current')) {
        const startYear = parseInt(duration.match(/\d{4}/));
        if (!isNaN(startYear)) {
          const years = currentYear - startYear;
          totalYears += years;
          console.log('Extracted years:', years);
          return;
        }
      }

      // Handle date ranges (e.g., "2015-2020", "Jan 2015 - Dec 2020")
      const dateRangeMatch = duration.match(/(\d{4}|\w+ \d{4})\s*(?:-|–|to)\s*(\d{4}|\w+ \d{4}|present|current)/i);
      if (dateRangeMatch) {
        const startDate = dateRangeMatch[1];
        const endDate = dateRangeMatch[2].toLowerCase();

        let startYear, endYear;
        
        // Parse start year
        if (startDate.match(/\d{4}/)) {
          startYear = parseInt(startDate);
        } else {
          const monthYear = startDate.split(' ');
          startYear = parseInt(monthYear[1]);
        }

        // Parse end year
        if (endDate === 'present' || endDate === 'current') {
          endYear = currentYear;
        } else if (endDate.match(/\d{4}/)) {
          endYear = parseInt(endDate);
        } else {
          const monthYear = endDate.split(' ');
          endYear = parseInt(monthYear[1]);
        }

        if (!isNaN(startYear) && !isNaN(endYear)) {
          const years = endYear - startYear;
          totalYears += years;
          console.log('Extracted years:', years);
          return;
        }
      }

      // Handle "X years" format
      const yearsMatch = duration.match(/(\d+)\s*(?:year|yr|yrs|years|y)/i);
      if (yearsMatch) {
        const years = parseInt(yearsMatch[1]);
        if (!isNaN(years)) {
          totalYears += years;
          console.log('Extracted years:', years);
          return;
        }
      }

      // Handle "X months" format
      const monthsMatch = duration.match(/(\d+)\s*(?:month|mo|mos|months)/i);
      if (monthsMatch) {
        const months = parseInt(monthsMatch[1]);
        if (!isNaN(months)) {
          const years = months / 12;
          totalYears += years;
          console.log('Extracted years:', years);
          return;
        }
      }

      console.log('No valid duration format found');
    });

    // Round to one decimal place for accuracy
    totalYears = Math.round(totalYears * 10) / 10;
    console.log('Total calculated years:', totalYears);
    return totalYears;
  };

  const fetchSavedReports = async (jobId) => {
    try {
      const response = await fetch(`${API_BASE_URL}/reports/${jobId}`);
      if (response.ok) {
        const reports = await response.json();
        setSavedReports(reports);
      }
    } catch (error) {
      console.error('Error fetching saved reports:', error);
    }
  };

  const exportShortlistedReport = async () => {
    try {
        if (!selectedJob?.job_id) {
            setError("Please select a job first");
            return;
        }

        setIsGeneratingReport(true);
        setError(null);

        // First, get the latest report for this job
        const reportsResponse = await fetch(`${API_BASE_URL}/reports/${selectedJob.job_id}`);
        if (!reportsResponse.ok) {
            if (reportsResponse.status === 404) {
                setError("No reports found for this job. Please run the matching process first.");
            } else {
                throw new Error(`Failed to fetch reports: ${reportsResponse.statusText}`);
            }
            return;
        }

        const reports = await reportsResponse.json();
        if (!reports || reports.length === 0) {
            setError("No reports found for this job. Please run the matching process first.");
            return;
        }

        // Get the most recent report
        const latestReport = reports[0];
        
        // Download the report
        const downloadResponse = await fetch(`${API_BASE_URL}/reports/download/${latestReport.id}`);
        if (!downloadResponse.ok) {
            throw new Error(`Failed to download report: ${downloadResponse.statusText}`);
        }

        // Create a blob from the response
        const blob = await downloadResponse.blob();
        
        // Create a download link
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = latestReport.filename;
        document.body.appendChild(a);
        a.click();
        
        // Cleanup
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        
        setError("Report downloaded successfully!");
        
    } catch (error) {
        console.error("Error downloading report:", error);
        setError(`Error downloading report: ${error.message}`);
    } finally {
        setIsGeneratingReport(false);
    }
};

  useEffect(() => {
    if (selectedJob?.job_id) {
      fetchSavedReports(selectedJob.job_id);
    }
  }, [selectedJob]);

  return (
    <ErrorBoundary>
      <div className="min-h-screen bg-gray-50">
        <nav className="bg-white shadow-sm">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex justify-between h-16">
              <div className="flex items-center">
                <h1 className="text-xl font-bold text-gray-900">TalentHub</h1>
              </div>
              <div className="flex items-center space-x-4">
                <button className="text-gray-600 hover:text-gray-900">Match Workspace</button>
                <button className="text-gray-600 hover:text-gray-900">Analytics</button>
                <button className="text-gray-600 hover:text-gray-900">Settings</button>
                <div className="w-8 h-8 bg-gradient-to-r from-emerald-400 to-emerald-600 rounded-full flex items-center justify-center text-white font-medium">U</div>
              </div>
            </div>
          </div>
        </nav>

        {error && (
          <div className="fixed top-4 right-4 bg-red-50 border-l-4 border-red-500 p-4 rounded-lg shadow-lg transform transition-all duration-300 ease-in-out">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <svg className="h-5 w-5 text-red-500" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                </svg>
              </div>
              <div className="ml-3">
                <p className="text-sm text-red-700">{error}</p>
              </div>
              <div className="ml-auto pl-3">
                <button onClick={() => setError("")} className="text-red-500 hover:text-red-700">
                  <span className="sr-only">Close</span>
                  <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
                  </svg>
                </button>
              </div>
            </div>
          </div>
        )}

        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="grid grid-cols-3 gap-6">
            {/* JD Upload + List Panel */}
            <div className="col-span-1">
              <div
                onDragOver={(e) => { e.preventDefault(); setHoverJD(true); }}
                onDragLeave={() => setHoverJD(false)}
                onDrop={(e) => { e.preventDefault(); const files = e.dataTransfer.files; setHoverJD(false); if (files.length) uploadFiles(files); }}
                className={`bg-white rounded-xl shadow-sm h-[calc(100vh-12rem)] flex flex-col ${hoverJD ? "ring-2 ring-blue-500" : ""}`}
              >
                <div className="p-4 border-b border-gray-100">
                  <div className="flex justify-between items-center">
                    <h2 className="text-lg font-semibold text-gray-900">Job Descriptions</h2>
                    {jdFiles.length > 0 && (
                      <button 
                        onClick={deleteAllJobs}
                        className="text-sm text-red-500 hover:text-red-700 font-medium"
                      >
                        Delete All
                      </button>
                    )}
                  </div>
                </div>

                <div className="p-4 flex-1 flex flex-col overflow-hidden">
                  <input
                    type="text"
                    placeholder="Search jobs..."
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    className="w-full px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />

                  <div
                    className={`mt-4 border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors ${
                      hoverJD ? "border-blue-500 bg-blue-50" : "border-gray-200 hover:border-gray-300"
                    }`}
                    onClick={() => jdInputRef.current.click()}
                  >
                    <svg className="mx-auto h-12 w-12 text-gray-400" stroke="currentColor" fill="none" viewBox="0 0 48 48">
                      <path d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                    <p className="mt-2 text-sm text-gray-600">Drag & drop job descriptions here</p>
                    <p className="mt-1 text-xs text-gray-500">or click to browse</p>
                    <input ref={jdInputRef} type="file" multiple className="hidden" onChange={(e) => uploadFiles(e.target.files)} />
                  </div>

                  {jdLoading && (
                    <div className="mt-4 flex items-center justify-center">
                      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
                    </div>
                  )}

                  <div className="mt-4 space-y-3 flex-1 overflow-y-auto">
                    {filteredJobs.map((job) => (
                      <div
                        key={job.job_id}
                        onClick={() => handleSelectJob(job)}
                        className={`p-4 rounded-lg cursor-pointer transition-all ${
                          selectedJob?.job_id === job.job_id
                            ? "bg-blue-50 border border-blue-200"
                            : "bg-white hover:bg-gray-100 border border-gray-100"
                        }`}
                      >
                        <div className="flex justify-between items-start">
                          <h3 className="text-sm font-medium text-gray-900 truncate">{job.filename}</h3>
                          <div className="flex items-center space-x-2">
                            <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                              job.parse_score >= 80 ? "bg-green-100 text-green-800" :
                              job.parse_score >= 50 ? "bg-yellow-100 text-yellow-800" :
                              "bg-red-100 text-red-800"
                            }`}>
                              {Math.round(job.parse_score)}%
                            </span>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                deleteJob(job.job_id);
                              }}
                              className="text-red-500 hover:text-red-700"
                            >
                              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                              </svg>
                            </button>
                          </div>
                        </div>
                        <div className="mt-2 flex items-center text-xs text-gray-500 space-x-4">
                          <span className="flex items-center">
                            <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                            </svg>
                            {job.word_count.toLocaleString()} words
                          </span>
                          <span className="flex items-center">
                            <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                            </svg>
                            {job.content_type.includes("pdf") ? "PDF" : job.content_type.includes("word") ? "DOCX" : "Unknown"}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            {/* Job Description Viewer Panel */}
            <div className="col-span-1">
              <div className="bg-white rounded-xl shadow-sm h-[calc(100vh-12rem)] flex flex-col">
                <div className="p-4 border-b border-gray-100">
                  <h2 className="text-lg font-semibold text-gray-900">Job Description</h2>
                </div>
                <div className="p-4 flex-1 flex flex-col overflow-hidden">
                  {selectedJob ? (
                    <div className="flex-1 flex flex-col overflow-hidden">
                      <div className="space-y-4">
                        <div className="bg-gray-50 rounded-lg p-4">
                          <h3 className="font-medium text-gray-900">{selectedJob.filename}</h3>
                          <div className="mt-2 flex items-center text-sm text-gray-500 space-x-4">
                            <span className="flex items-center">
                              <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                              </svg>
                              {selectedJob.word_count.toLocaleString()} words
                            </span>
                            <span className="flex items-center">
                              <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                              </svg>
                              Parse Score: {selectedJob.parse_score.toFixed(2)}
                            </span>
                          </div>
                        </div>
                        <div className="space-y-3">
                          <div className="flex space-x-4 mb-4">
                            <button
                              onClick={matchCandidates}
                              disabled={!selectedJob || isMatching}
                              className={`px-4 py-2 rounded ${
                                !selectedJob || isMatching
                                  ? 'bg-gray-400 cursor-not-allowed'
                                  : 'bg-blue-500 hover:bg-blue-600'
                              } text-white`}
                            >
                              {isMatching ? 'Matching...' : 'Match Candidates'}
                            </button>
                          </div>
                          <div className="relative">
                            <select
                              value={selectedCandidateForMatch || ""}
                              onChange={(e) => setSelectedCandidateForMatch(e.target.value || null)}
                              className="w-full p-2.5 border border-gray-200 rounded-lg bg-white text-gray-700 focus:ring-2 focus:ring-blue-500 focus:border-transparent appearance-none"
                            >
                              <option value="">Match All Candidates</option>
                              {candidates.map((candidate) => (
                                <option key={candidate.candidate_id} value={candidate.candidate_id}>
                                  {candidate.extracted_info?.name || candidate.filename}
                                </option>
                              ))}
                            </select>
                            <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-2 text-gray-700">
                              <svg className="fill-current h-4 w-4" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20">
                                <path d="M9.293 12.95l.707.707L15.657 8l-1.414-1.414L10 10.828 5.757 6.586 4.343 8z" />
                              </svg>
                            </div>
                          </div>
                        </div>
                      </div>
                      {jobLoading ? (
                        <div className="flex-1 flex items-center justify-center">
                          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
                        </div>
                      ) : (
                        <div className="flex-1 mt-4 overflow-y-auto">
                          <div className="bg-gray-50 rounded-lg p-4 whitespace-pre-wrap text-sm text-gray-700">
                            {jobText}
                          </div>
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="flex-1 flex items-center justify-center text-gray-500">
                      <div className="text-center">
                        <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                        </svg>
                        <p className="mt-2">Select a job description to view details</p>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* CV Upload + List Panel */}
            <div className="col-span-1">
              <div
                onDragOver={(e) => { e.preventDefault(); setHoverCV(true); }}
                onDragLeave={() => setHoverCV(false)}
                onDrop={(e) => { e.preventDefault(); const files = e.dataTransfer.files; setHoverCV(false); if (files.length) uploadCVs(files); }}
                className={`bg-white rounded-xl shadow-sm h-[calc(100vh-12rem)] flex flex-col ${hoverCV ? "ring-2 ring-blue-500" : ""}`}
              >
                <div className="p-4 border-b border-gray-100">
                  <div className="flex justify-between items-center">
                    <h2 className="text-lg font-semibold text-gray-900">Candidate CVs</h2>
                    {candidates.length > 0 && (
                      <button 
                        onClick={deleteAllCandidates}
                        className="text-sm text-red-500 hover:text-red-700 font-medium"
                      >
                        Delete All
                      </button>
                    )}
                  </div>
                </div>

                <div className="p-4 flex-1 flex flex-col overflow-hidden">
                  <input
                    type="text"
                    placeholder="Search CVs..."
                    value={cvSearch}
                    onChange={(e) => setCvSearch(e.target.value)}
                    className="w-full px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />

                  <div
                    className={`mt-4 border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors ${
                      hoverCV ? "border-blue-500 bg-blue-50" : "border-gray-200 hover:border-gray-300"
                    }`}
                    onClick={() => cvInputRef.current.click()}
                  >
                    <svg className="mx-auto h-12 w-12 text-gray-400" stroke="currentColor" fill="none" viewBox="0 0 48 48">
                      <path d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                    <p className="mt-2 text-sm text-gray-600">Drag & drop CVs here</p>
                    <p className="mt-1 text-xs text-gray-500">or click to browse</p>
                    <input ref={cvInputRef} type="file" multiple className="hidden" onChange={(e) => uploadCVs(e.target.files)} />
                  </div>

                  {cvLoading && (
                    <div className="mt-4 flex items-center justify-center">
                      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
                    </div>
                  )}

                  {/* CV Summary Cards - Fixed Height with Scroll */}
                  <div className="mt-4 flex-1 overflow-y-auto max-h-[40vh]">
                    <div className="space-y-3">
                      {candidates
                        .filter(cv => cv.filename.toLowerCase().includes(cvSearch.toLowerCase()))
                        .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
                        .map((candidate) => (
                          <div
                            key={candidate.candidate_id}
                            onClick={() => handleSelectCandidate(candidate)}
                            className={`p-4 rounded-lg cursor-pointer transition-all ${
                              selectedCandidate?.candidate_id === candidate.candidate_id
                                ? "bg-blue-50 border border-blue-200"
                                : "bg-white hover:bg-gray-100 border border-gray-100"
                            }`}
                          >
                            <div className="flex justify-between items-start">
                              <h3 className="text-sm font-medium text-gray-900 truncate">
                                {candidate.extracted_info?.name || candidate.filename}
                              </h3>
                              <div className="flex items-center space-x-2">
                                <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                                  candidate.parse_score >= 80 ? "bg-green-100 text-green-800" :
                                  candidate.parse_score >= 50 ? "bg-yellow-100 text-yellow-800" :
                                  "bg-red-100 text-red-800"
                                }`}>
                                  {Math.round(candidate.parse_score)}%
                                </span>
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    deleteCandidate(candidate.candidate_id);
                                  }}
                                  className="text-red-500 hover:text-red-700"
                                >
                                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                  </svg>
                                </button>
                              </div>
                            </div>
                            <div className="mt-2 flex items-center text-xs text-gray-500 space-x-4">
                              <span className="flex items-center">
                                <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                                </svg>
                                {candidate.extracted_info?.experience?.length > 0 
                                  ? `${candidate.extracted_info.experience.length} positions` 
                                  : 'Experience not specified'}
                              </span>
                              <span className="flex items-center">
                                <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                                </svg>
                                {candidate.extracted_info?.location || 'Location not specified'}
                              </span>
                            </div>
                            {candidate.extracted_info?.experience?.length > 0 && (
                              <div className="mt-2 text-xs text-gray-600">
                                <span className="font-medium">Current Role:</span> {candidate.extracted_info.experience[0].job_title}
                                {candidate.extracted_info.experience[0].company && (
                                  <span className="text-gray-500"> at {candidate.extracted_info.experience[0].company}</span>
                                )}
                              </div>
                            )}
                            {candidate.extracted_info?.skills?.length > 0 && (
                              <div className="mt-2 flex flex-wrap gap-1">
                                {candidate.extracted_info.skills.slice(0, 3).map((skill, index) => (
                                  <span key={index} className="bg-blue-50 text-blue-700 px-2 py-0.5 rounded-full text-xs">
                                    {skill}
                                  </span>
                                ))}
                                {candidate.extracted_info.skills.length > 3 && (
                                  <span className="text-gray-400 text-xs">
                                    +{candidate.extracted_info.skills.length - 3}
                                  </span>
                                )}
                              </div>
                            )}
                          </div>
                        ))}
                    </div>
                  </div>

                  {/* Matching Results Section - Fixed Height with Scroll */}
                  {matchingResults && (
                    <div className="mt-4 flex-1 overflow-y-auto max-h-[40vh]">
                      <h2 className="text-xl font-semibold mb-4">Matching Results</h2>
                      <div className="bg-white rounded-lg shadow p-4">
                        {matchingResults.matches && matchingResults.matches.length > 0 ? (
                          <div className="space-y-4">
                            {matchingResults.matches
                              .sort((a, b) => {
                                const scoreA = (a.python_score + (a.claude_score || 0)) / 2;
                                const scoreB = (b.python_score + (b.claude_score || 0)) / 2;
                                return scoreB - scoreA;
                              })
                              .map((match, index) => (
                                <div 
                                  key={index} 
                                  className="border rounded-lg p-4 cursor-pointer hover:bg-gray-50 transition-colors"
                                  onClick={() => setSelectedMatch(match)}
                                >
                                  <div className="flex justify-between items-start">
                                    <div>
                                      <h3 className="font-semibold">{match.candidate_name}</h3>
                                      <p className="text-sm text-gray-600">System Match: {match.python_score}%</p>
                                      {match.claude_score && (
                                        <p className="text-sm text-gray-600">AI Review: {match.claude_score}%</p>
                                      )}
                                    </div>
                                    <button
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        toggleShortlist(match.candidate_id);
                                      }}
                                      className={`px-3 py-1 rounded ${
                                        match.shortlist
                                          ? 'bg-green-500 text-white'
                                          : 'bg-gray-200 text-gray-700'
                                      }`}
                                    >
                                      {match.shortlist ? 'Shortlisted' : 'Shortlist'}
                                    </button>
                                  </div>
                                  {match.claude_analysis && (
                                    <div className="mt-2">
                                      <h4 className="font-medium">Claude Analysis:</h4>
                                      <div className="text-sm space-y-2">
                                        {typeof match.claude_analysis === 'string' ? (
                                          <p>{match.claude_analysis}</p>
                                        ) : (
                                          <>
                                            {match.claude_analysis.strengths && (
                                              <div>
                                                <p className="font-medium text-green-600">Strengths:</p>
                                                <ul className="list-disc list-inside ml-4">
                                                  {match.claude_analysis.strengths.map((strength, idx) => (
                                                    <li key={idx}>{strength}</li>
                                                  ))}
                                                </ul>
                                              </div>
                                            )}
                                            {match.claude_analysis.gaps && (
                                              <div>
                                                <p className="font-medium text-red-600">Gaps:</p>
                                                <ul className="list-disc list-inside ml-4">
                                                  {match.claude_analysis.gaps.map((gap, idx) => (
                                                    <li key={idx}>{gap}</li>
                                                  ))}
                                                </ul>
                                              </div>
                                            )}
                                          </>
                                        )}
                                      </div>
                                    </div>
                                  )}
                                </div>
                              ))}
                          </div>
                        ) : (
                          <p className="text-gray-500">No matches found</p>
                        )}
                      </div>
                      <div className="mt-4 flex justify-end">
                        <button
                          onClick={exportShortlistedReport}
                          disabled={!selectedJob || isGeneratingReport}
                          className={`px-4 py-2 rounded ${
                            !selectedJob || isGeneratingReport
                              ? 'bg-gray-400 cursor-not-allowed'
                              : 'bg-blue-500 hover:bg-blue-600'
                          } text-white`}
                        >
                          {isGeneratingReport ? 'Generating Report...' : 'Generate Report'}
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* CV Preview Side Panel */}
        {selectedCandidate && (
          <div className="fixed inset-y-0 right-0 w-1/3 bg-white shadow-lg transform transition-transform duration-300 ease-in-out">
            <div className="h-full flex flex-col">
              <div className="p-4 border-b border-gray-100 flex justify-between items-center">
                <h3 className="text-lg font-semibold text-gray-900">Candidate Information</h3>
                <button
                  onClick={() => setSelectedCandidate(null)}
                  className="text-gray-500 hover:text-gray-700"
                >
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
              <div className="flex-1 overflow-y-auto p-4">
                {candidateLoading ? (
                  <div className="flex items-center justify-center py-8">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
                  </div>
                ) : (
                  <div className="text-sm text-gray-700 space-y-4">
                    {/* Basic Information */}
                    <div className="bg-gray-50 rounded-lg p-4">
                      <h4 className="font-medium text-gray-900 mb-2">Basic Information</h4>
                      <div className="grid grid-cols-2 gap-2">
                        {selectedCandidate.extracted_info?.name && (
                          <div>
                            <span className="text-gray-500">Name:</span> {selectedCandidate.extracted_info.name}
                          </div>
                        )}
                        {selectedCandidate.extracted_info?.email && (
                          <div>
                            <span className="text-gray-500">Email:</span> {selectedCandidate.extracted_info.email}
                          </div>
                        )}
                        {selectedCandidate.extracted_info?.phone && (
                          <div>
                            <span className="text-gray-500">Phone:</span> {selectedCandidate.extracted_info.phone}
                          </div>
                        )}
                        {selectedCandidate.extracted_info?.location && (
                          <div>
                            <span className="text-gray-500">Location:</span> {selectedCandidate.extracted_info.location}
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Summary */}
                    {selectedCandidate.extracted_info?.summary && (
                      <div className="bg-gray-50 rounded-lg p-4">
                        <h4 className="font-medium text-gray-900 mb-2">Summary</h4>
                        <p className="whitespace-pre-wrap">{selectedCandidate.extracted_info.summary}</p>
                      </div>
                    )}

                    {/* Skills */}
                    {selectedCandidate.extracted_info?.skills?.length > 0 && (
                      <div className="bg-gray-50 rounded-lg p-4">
                        <h4 className="font-medium text-gray-900 mb-2">Skills</h4>
                        <div className="flex flex-wrap gap-2">
                          {selectedCandidate.extracted_info.skills.map((skill, index) => (
                            <span key={index} className="bg-blue-50 text-blue-700 px-2 py-0.5 rounded-full text-xs">
                              {skill}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Education */}
                    {selectedCandidate.extracted_info?.education?.length > 0 && (
                      <div className="bg-gray-50 rounded-lg p-4">
                        <h4 className="font-medium text-gray-900 mb-2">Education</h4>
                        <div className="space-y-2">
                          {selectedCandidate.extracted_info.education.map((edu, index) => (
                            <div key={index} className="border-l-2 border-blue-200 pl-2">
                              <div className="font-medium">{edu.degree}</div>
                              <div className="text-gray-600">{edu.school}</div>
                              <div className="text-gray-500 text-xs">{edu.dates}</div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Experience */}
                    {selectedCandidate.extracted_info?.experience?.length > 0 && (
                      <div className="bg-gray-50 rounded-lg p-4">
                        <h4 className="font-medium text-gray-900 mb-2">Experience</h4>
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

                    {/* Languages */}
                    {selectedCandidate.extracted_info?.languages?.length > 0 && (
                      <div className="bg-gray-50 rounded-lg p-4">
                        <h4 className="font-medium text-gray-900 mb-2">Languages</h4>
                        <div className="flex flex-wrap gap-2">
                          {selectedCandidate.extracted_info.languages.map((lang, index) => (
                            <span key={index} className="bg-gray-100 text-gray-800 px-2 py-0.5 rounded-full text-xs">
                              {lang}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Match Details Side Panel */}
        {selectedMatch && (
          <div className="fixed inset-y-0 right-0 w-1/3 bg-white shadow-lg transform transition-transform duration-300 ease-in-out">
            <div className="h-full flex flex-col">
              <div className="p-4 border-b border-gray-100 flex justify-between items-center">
                <h3 className="text-lg font-semibold text-gray-900">Match Details</h3>
                <button
                  onClick={() => setSelectedMatch(null)}
                  className="text-gray-500 hover:text-gray-700"
                >
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
              <div className="flex-1 overflow-y-auto p-4">
                <div className="text-sm text-gray-700 space-y-4">
                  <div className="bg-gray-50 rounded-lg p-4">
                    <h4 className="font-medium text-gray-900 mb-2">Scores</h4>
                    <div className="space-y-2">
                      <div className="flex justify-between">
                        <span>System Match:</span>
                        <span className="font-medium">{selectedMatch.python_score.toFixed(2)}</span>
                      </div>
                      <div className="flex justify-between">
                        <span>AI Review:</span>
                        <span className="font-medium">{selectedMatch.claude_score?.toFixed(2) || "Not available"}</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Overall Score:</span>
                        <span className="font-medium">
                          {selectedMatch.claude_score 
                            ? ((selectedMatch.python_score + selectedMatch.claude_score) / 2).toFixed(2)
                            : selectedMatch.python_score.toFixed(2)}
                        </span>
                      </div>
                      {selectedMatch.shortlist !== undefined && (
                        <div className="flex justify-between">
                          <span>Shortlist:</span>
                          <span className={`font-medium ${selectedMatch.shortlist ? "text-green-600" : "text-red-600"}`}>
                            {selectedMatch.shortlist ? "Yes" : "No"}
                          </span>
                        </div>
                      )}
                    </div>
                  </div>

                  {selectedMatch.strengths && selectedMatch.strengths.length > 0 && (
                    <div className="bg-gray-50 rounded-lg p-4">
                      <h4 className="font-medium text-gray-900 mb-2">Strengths</h4>
                      <ul className="list-disc list-inside text-sm space-y-1">
                        {selectedMatch.strengths.map((strength, i) => (
                          <li key={i}>{strength}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {selectedMatch.gaps && selectedMatch.gaps.length > 0 && (
                    <div className="bg-gray-50 rounded-lg p-4">
                      <h4 className="font-medium text-gray-900 mb-2">Gaps</h4>
                      <ul className="list-disc list-inside text-sm space-y-1">
                        {selectedMatch.gaps.map((gap, i) => (
                          <li key={i}>{gap}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Add this section to display saved reports */}
        {savedReports.length > 0 && (
          <div className="mt-4">
            <h3 className="text-lg font-semibold mb-2">Saved Reports</h3>
            <div className="space-y-2">
              {savedReports.map((report) => (
                <div key={report.id} className="flex items-center justify-between bg-gray-50 p-3 rounded">
                  <div>
                    <p className="font-medium">{report.filename}</p>
                    <p className="text-sm text-gray-500">
                      Created: {new Date(report.created_at).toLocaleString()}
                    </p>
                  </div>
                  <a
                    href={`${API_BASE_URL}/reports/download/${report.id}`}
                    className="text-blue-500 hover:text-blue-700"
                    download
                  >
                    Download
                  </a>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </ErrorBoundary>
  );
}