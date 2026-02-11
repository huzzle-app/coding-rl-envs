# frozen_string_literal: true

module Api
  module V1
    class TasksController < ApplicationController
      before_action :set_project, only: [:index, :create]
      before_action :set_task, only: [:show, :update, :destroy, :assign, :complete, :reopen]

      def index
        
        @tasks = @project.tasks.includes(:assignee, :creator)

        
        if params[:status]
          @tasks = @tasks.where(status: params[:status])
        end

        render json: @tasks
      end

      def show
        
        @task = Task.includes(
          :assignee, :creator, :project, :milestone,
          :subtasks, :comments, :attachments,
          dependencies: [:assignee]
        ).find(params[:id])

        render json: @task, include: [:comments, :subtasks]
      end

      def create
        @task = TaskService.new(current_user).create(@project, task_params)

        if @task&.persisted?
          render json: @task, status: :created
        else
          
          render json: { error: @task&.errors&.full_messages || 'Creation failed' },
                 status: :unprocessable_entity
        end
      end

      def update
        authorize @task

        if @task.update(task_params)
          render json: @task
        else
          render json: { errors: @task.errors }, status: :unprocessable_entity
        end
      end

      def destroy
        authorize @task
        @task.destroy
        head :no_content
      end

      def assign
        authorize @task, :update?

        assignee = User.find(params[:assignee_id])

        
        @task.assign_to(assignee)

        render json: @task
      rescue ActiveRecord::RecordNotFound
        render json: { error: 'User not found' }, status: :not_found
      end

      def complete
        authorize @task, :update?

        if @task.may_complete?
          @task.complete!
          render json: @task
        else
          render json: { error: 'Task cannot be completed' }, status: :unprocessable_entity
        end
      end

      def reopen
        authorize @task, :update?

        if @task.may_reopen?
          @task.reopen!
          render json: @task
        else
          render json: { error: 'Task cannot be reopened' }, status: :unprocessable_entity
        end
      end

      private

      def set_project
        @project = Project.find(params[:project_id])
        authorize @project, :show?
      end

      def set_task
        @task = Task.find(params[:id])
      end

      def task_params
        params.require(:task).permit(
          :title, :description, :status, :priority,
          :due_date, :estimated_hours, :assignee_id,
          :milestone_id, :parent_id,
          
          :creator_id, :completed_at, :position,
          tags: [], metadata: {}
        )
      end
    end
  end
end
