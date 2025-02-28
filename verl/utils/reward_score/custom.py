# Copyright 2024 Bytedance Ltd. and/or its affiliates
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import re
from typing import List, Tuple, Optional


def validate_response_structure(processed_response: str) -> bool:
    """Performs comprehensive validation of response structure.
    
    Args:
        processed_response: Processed response string from the model
        
    Returns:
        Boolean indicating whether all formatting requirements are met
    """
    print("\n[Structure Validation]")
    validation_passed = True

    # Check required tags
    tags = {
        'think_start': ('<think>', 1),
        'think_end': ('</think>', 1),
        'answer_start': ('<answer>', 1),
        'answer_end': ('</answer>', 1)
    }

    positions = {}
    for tag_name, (tag_str, expected_count) in tags.items():
        count = processed_response.count(tag_str)
        positions[tag_name] = pos = processed_response.find(tag_str)
        
        print(f"  {tag_str}: count={count}, position={pos}")
        
        if count != expected_count:
            print(f"  [Error] {tag_str} appears {count} times (expected {expected_count})")
            validation_passed = False

    # Verify tag order
    if (positions['think_start'] > positions['think_end'] or
        positions['think_end'] > positions['answer_start'] or
        positions['answer_start'] > positions['answer_end']):
        print("  [Error] Incorrect tag order: Expected <think>...</think><answer>...</answer>")
        validation_passed = False
    else:
        print("  Tag sequence validation passed")

    return validation_passed


def extract_box_contents(answer: str) -> List[str]:
    """提取 \box{} 中的内容，并验证是否为数字"""

    def is_number(s: str) -> bool:
        number_pattern = r'^-?\d*\.?\d+$|^-?\d+\/\d+$'
        return bool(re.match(number_pattern, s))

    box_pattern = r'\\boxed\{([^}]+)\}'
    matches = re.findall(box_pattern, answer)

    result = []
    for content in matches:
        content = content.strip()
        if is_number(content):
            result.append(content)
    return result


def extract_solution(solution_str: str) -> Tuple[Optional[str], str]:
    """Extracts the final answer from the model's response string.
    
    Args:
        solution_str: Raw response string from the language model
        
    Returns:
        Tuple containing (extracted_answer, processed_string)
    """

    if "Assistant:" in solution_str:                                               # base model
        processed_str = solution_str.split("Assistant:", 1)[1]
    elif "<|im_start|>assistant" in solution_str:                                  # instruct model
        response_pattern = r'<\|im_start\|>assistant(.*?)<\|im_end\|>'
        match = re.search(response_pattern, solution_str, re.DOTALL)
        if match:
            processed_str = match.group(1).strip()
        else:
            print("[Error] Failed to Parse Model Response From {solution_str}")
            return None, solution_str
    else:
        print("[Error] Failed to locate model response header")
        return None, solution_str

    # Extract final answer using XML-style tags
    answer_pattern = r'<answer>(.*?)</answer>'
    matches = list(re.finditer(answer_pattern, processed_str, re.DOTALL))
    
    if not matches:
        print("[Error] No valid answer tags found")
        return None, processed_str
        
    final_answer = matches[-1].group(1).strip()
    return final_answer, processed_str


def compute_answer_score(solution_str, ground_truth: str, format_reward: float=0., score: float=1.):
    """Computes comprehensive score for model response.
    
    Args:
        solution_str: Raw model response string
        ground_truth: Dictionary containing ground truth data
        format_reward: Points awarded/deducted for format correctness
        answer_reward: Points awarded/deducted for answer correctness
        
    Returns:
        answer reward
    """
    print("\n" + "="*80)
    print(" Processing New Sample ".center(80, '='))
    print(solution_str)

    answer_text, processed_response = extract_solution(solution_str)
    print(f"\n[Model Response]\n{processed_response}")

    if answer_text is None:
        return 0

    box_contents = extract_box_contents(answer_text)
    
    print(f"\n[Content Validation]")
    print(f"  Expected: {ground_truth}")
    print(f"  Predicted: {box_contents}")

    if len(box_contents) == 0:
        return 0.
    else:
        if ground_truth in box_contents:
            return score
        else:
            return format_reward


def compute_accuracy_format_score(solution_str, ground_truth: str, format_reward: float=0.1, answer_reward: float = 1.):
    """Computes comprehensive score for model response.
    
    Args:
        solution_str: Raw model response string
        ground_truth: Dictionary containing ground truth data
        format_reward: Points awarded/deducted for format correctness
        answer_reward: Points awarded/deducted for answer correctness
        
    Returns:
        Total score (sum of format and answer rewards)
    """
    print("\n" + "="*80)
    print(" Processing New Sample ".center(80, '='))
    print(f"[Ground Truth]: {ground_truth}")

    answer_text, processed_response = extract_solution(solution_str)
    print(f"\n[Model Response]\n{processed_response}")

    format_correct = validate_response_structure(processed_response)
    format_score = format_reward if format_correct else -abs(format_reward) * 10
    print(f"\n  Format validation: {'PASS' if format_correct else 'FAIL'}")
    print(f"  Format score: {format_score}")

    if format_correct and answer_text:
        box_contents = extract_box_contents(answer_text)
        print(f"\n[Content Validation]")
        print(f"  Answered: {answer_text}")
        print(f"  Expected: {ground_truth}")
        print(f"  Predicted: {box_contents}")
        if ground_truth in box_contents:
            if len(box_contents) == 1:
                answer_score = answer_reward * 2
            else:
                answer_score = answer_reward * 1.5
                print(f"Multiple Boxes: {answer_reward}")
        else:
            if len(box_contents) == 1:
                answer_score = -1.5 * answer_reward 
            else:
                answer_score = -2 * answer_reward 
    else:
        answer_score = -2
        print( "Fail to parse answer")

    total_score = format_score + answer_score
    print("\n" + "-"*80)
    print(f" Final Score ".center(80, '-'))
    print(f"  Format: {format_score}")
    print(f"  Answer: {answer_score}")
    print(f"  Total: {total_score}")
    print("="*80 + "\n")

    return total_score



if __name__  == '__main__':
    answer_text = " \\boxed{75} "
    bbox_content = extract_box_contents(answer_text)
    print(bbox_content)

    
