import React, { useState, useEffect } from "react"; // [!!] Added useEffect

export interface CourseData {
  id: string;
  code: string;
  score: string;
  description?: string;
  icon?: string;
}

export interface ResultCardProps {
  course: CourseData;
  expanded?: boolean;
  onClick?: (id: string) => void;
}

const ResultCard: React.FC<ResultCardProps> = ({
  course,
  expanded = false,
  onClick,
}) => {
  // [!!] Added dark mode state listener
  const [isDark, setIsDark] = useState<boolean>(
    document.documentElement.classList.contains("dark"),
  );

  useEffect(() => {
    const observer = new MutationObserver(() => {
      setIsDark(document.documentElement.classList.contains("dark"));
    });
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["class"],
    });
    return () => observer.disconnect();
  }, []);

  // [!!] Use isDark state for colors
  const pillBg = isDark ? "dark:bg-neutral-800" : "bg-[#F5F6F8]";
  const pillHover = isDark ? "dark:hover:bg-neutral-700" : "hover:bg-[#ECEDEF]";
  const textMuted = isDark ? "dark:text-neutral-400" : "text-[#6B6C6E]";
  const titleColor = isDark ? "dark:text-neutral-100" : "text-[#111827]";
  const arrowColor = isDark ? textMuted : titleColor; // Arrow is muted in dark, dark in light

  // [!!] Use isDark state for background gradient/color
  const getBackgroundStyle = () => {
    if (expanded) {
      return isDark
        ? "linear-gradient(180deg, #262626 0%, #171717 100%)" // neutral-800 to neutral-900
        : "linear-gradient(180deg, #FFFFFF 0%, #F9FAFB 100%)"; // white to gray-50
    } else {
      return isDark ? "#262626" : "#F5F6F8"; // neutral-800 vs specific light gray
    }
  };

  return (
    <div className="w-full mb-4 last:mb-0">
      <div
        onClick={() => onClick?.(course.id)}
        className={`
     w-full cursor-pointer select-none
     transition-all duration-500 ease-[cubic-bezier(0.25,0.8,0.25,1)]
     ${pillBg} ${pillHover}
     shadow-sm hover:shadow-md
     dark:shadow-neutral-900 dark:hover:shadow-neutral-700/50
    `}
        style={{
          borderRadius: expanded ? "20px" : "9999px",
          padding: expanded ? "16px" : "12px 16px",
          background: getBackgroundStyle(), // Use dynamic background
          transform: expanded ? "scale(1.02)" : "scale(1)",
          transitionProperty:
            "border-radius, padding, background, transform, box-shadow",
          transitionDuration: "500ms",
          transitionTimingFunction: "cubic-bezier(0.25, 0.8, 0.25, 1)",
        }}
      >
        <div className="flex items-center w-full">
          {/* Icon background */}
          <div
            className={`flex-shrink-0 w-8 h-8 rounded-full ${isDark ? "bg-neutral-600" : "bg-gray-300"} mr-3 overflow-hidden`}
          >
            {course.icon && (
              <img
                src={course.icon}
                alt={course.code}
                className="w-full h-full object-cover"
              />
            )}
          </div>

          {/* Course Code */}
          <div
            className={`flex-1 font-semibold ${titleColor} truncate mr-3`}
            title={course.code}
          >
            {course.code}
          </div>

          {/* Score */}
          <div
            className={`flex-shrink-0 font-medium ${titleColor} ml-auto pl-3`}
          >
            {course.score}
          </div>

          {/* Arrow Icon */}
          <div className={`flex-shrink-0 ml-2 ${arrowColor}`}>
            {" "}
            {/* [!!] Use arrowColor variable */}
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className={`h-5 w-5 transition-transform duration-500 ease-in-out ${expanded ? "rotate-180" : "rotate-0"
                }`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M19 9l-7 7-7-7"
              />
            </svg>
          </div>
        </div>

        {/* Description */}
        <div
          className={`overflow-hidden transition-all duration-500 ease-in-out`}
          style={{
            maxHeight: expanded ? "300px" : "0px",
            opacity: expanded ? 1 : 0,
            marginTop: expanded ? "12px" : "0px",
          }}
        >
          <p className={`${textMuted} text-sm px-1`}>
            {course.description
              ? course.description
              : "No description provided."}
          </p>
        </div>
      </div>
    </div>
  );
};

// ResultCardsList remains unchanged
export interface ResultCardsListProps {
  courses: CourseData[];
  expandedId: string | null;
  onCardClick: (id: string) => void;
}

export const ResultCardsList: React.FC<ResultCardsListProps> = ({
  courses,
  expandedId,
  onCardClick,
}) => {
  return (
    <div className="flex flex-col space-y-4">
      {courses.map((c) => (
        <ResultCard
          key={c.id}
          course={c}
          expanded={expandedId === c.id}
          onClick={onCardClick}
        />
      ))}
    </div>
  );
};

export default ResultCard;
